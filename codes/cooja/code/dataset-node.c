#include "contiki.h"
#include "contiki-net.h"

#include "sys/node-id.h"
#include "sys/energest.h"

#include "net/netstack.h"
#include "net/routing/routing.h"

#include "net/ipv6/simple-udp.h"
#include "net/ipv6/uip-ds6.h"
#include "net/ipv6/uip-ds6-nbr.h"
#include "net/ipv6/uip-ds6-route.h"
#include "net/ipv6/uiplib.h"

#include "dev/radio.h"

#include "net/routing/rpl-lite/rpl.h"

#include "dataset-stats.h"

#include <stdio.h>
#include <string.h>

#define UDP_CLIENT_PORT 8765
#define UDP_SERVER_PORT 5678

#define APP_INTERVAL (5 * CLOCK_SECOND)
#define LOG_INTERVAL (10 * CLOCK_SECOND)

#ifndef ATTACK_TYPE
#define ATTACK_TYPE 0
#endif

#ifndef ATTACK_START
#define ATTACK_START 300
#endif
#ifndef ATTACK_END
#define ATTACK_END   600
#endif

volatile uint32_t dio_rx_count = 0;
volatile uint32_t dio_tx_count = 0;
volatile uint32_t dao_rx_count = 0;
volatile uint32_t dao_tx_count = 0;

static uint32_t app_rx_count = 0;
static uint32_t app_tx_count = 0;

static uint32_t last_app_rx = 0;
static uint32_t last_app_tx = 0;

static uint64_t last_cpu = 0, last_lpm = 0, last_tx = 0, last_rx = 0;

static struct simple_udp_connection udp_conn;

/* Helpers */

static int
is_attack_active(void)
{
  uint32_t now_s = clock_time() / CLOCK_SECOND;
  return (ATTACK_TYPE != 0) &&
         (now_s >= ATTACK_START) &&
         (now_s <= ATTACK_END);
}

static void
get_ipv6_str(char *buf, size_t buf_len)
{
  uip_ds6_addr_t *addr = uip_ds6_get_global(ADDR_PREFERRED);
  if(addr != NULL) {
    uiplib_ipaddr_snprint(buf, buf_len, &addr->ipaddr);
  } else {
    snprintf(buf, buf_len, "NONE");
  }
}

static void
get_parent_ipv6_str(char *buf, size_t buf_len)
{
  uip_ds6_defrt_t *defrt = uip_ds6_defrt_choose();
  if(defrt != NULL) {
    uiplib_ipaddr_snprint(buf, buf_len, &defrt->ipaddr);
  } else {
    snprintf(buf, buf_len, "NONE");
  }
}

static uint16_t
get_rpl_rank(void)
{
  rpl_instance_t *inst = rpl_get_default_instance();
  if(inst != NULL) {
    return inst->dag.rank;
  }
  return 0;
}

static void
get_neighbor_list(char *buf, size_t buf_len)
{
  uip_ds6_nbr_t *nbr;
  int first = 1;
  size_t used = 0;

  buf[0] = '\0';

  for(nbr = uip_ds6_nbr_head(); nbr != NULL; nbr = uip_ds6_nbr_next(nbr)) {
    char addr_str[64];
    uiplib_ipaddr_snprint(addr_str, sizeof(addr_str), &nbr->ipaddr);

    int n = snprintf(buf + used, buf_len - used,
                     "%s%s", first ? "" : "|", addr_str);
    if(n <= 0) {
      break;
    }
    if((size_t)n >= buf_len - used) {
      used = buf_len - 1;
      break;
    }
    used += (size_t)n;
    first = 0;
  }

  if(first) {
    snprintf(buf, buf_len, "NONE");
  }
}

static int16_t
get_rssi(void)
{
  radio_value_t val;
  if(NETSTACK_RADIO.get_value(RADIO_PARAM_RSSI, &val) == RADIO_RESULT_OK) {
    return (int16_t)val;
  }
  return 0;
}

static void
get_energy(double *cpu_s, double *lpm_s, double *tx_s, double *rx_s)
{
  energest_flush();

  uint64_t cpu = energest_type_time(ENERGEST_TYPE_CPU);
  uint64_t lpm = energest_type_time(ENERGEST_TYPE_LPM);
  uint64_t tx = energest_type_time(ENERGEST_TYPE_TRANSMIT);
  uint64_t rx = energest_type_time(ENERGEST_TYPE_LISTEN);

  *cpu_s = (double)(cpu - last_cpu) / ENERGEST_SECOND;
  *lpm_s = (double)(lpm - last_lpm) / ENERGEST_SECOND;
  *tx_s  = (double)(tx  - last_tx)  / ENERGEST_SECOND;
  *rx_s  = (double)(rx  - last_rx)  / ENERGEST_SECOND;

  last_cpu = cpu;
  last_lpm = lpm;
  last_tx  = tx;
  last_rx  = rx;
}

static float
get_plr_interval(void)
{
  uint32_t tx_now = app_tx_count;
  uint32_t rx_now = app_rx_count;
  uint32_t tx_diff = tx_now - last_app_tx;
  uint32_t rx_diff = rx_now - last_app_rx;

  last_app_tx = tx_now;
  last_app_rx = rx_now;

  if(tx_diff == 0) {
    return 0.0f;
  }
  if(rx_diff >= tx_diff) {
    return 0.0f;
  }
  return (float)(tx_diff - rx_diff) / (float)tx_diff;
}

static void
maybe_run_attack_logic(void)
{
  if(!is_attack_active()) {
    return;
  }

  switch(ATTACK_TYPE) {
  case 1: /* sinkhole */         break;
  case 2: /* rank */             break;
  case 3: /* blackhole */        break;
  case 4: /* selective forward */break;
  case 5: /* sybil */            break;
  case 6: /* jamming */          break;
  case 7: /* spoofing */         break;
  default:                        break;
  }
}

static void
udp_rx_callback(struct simple_udp_connection *c,
                const uip_ipaddr_t *sender_addr,
                uint16_t sender_port,
                const uip_ipaddr_t *receiver_addr,
                uint16_t receiver_port,
                const uint8_t *data,
                uint16_t datalen)
{
  (void)c; (void)sender_addr; (void)sender_port;
  (void)receiver_addr; (void)receiver_port; (void)data; (void)datalen;

  app_rx_count++;
}

PROCESS(dataset_node_process, "Dataset RPL node");
AUTOSTART_PROCESSES(&dataset_node_process);

PROCESS_THREAD(dataset_node_process, ev, data)
{
  static struct etimer app_timer;
  static struct etimer log_timer;

  PROCESS_BEGIN();

  printf("NODE_START ID=%u ATTACK_TYPE=%d START=%d END=%d\n",
         node_id, ATTACK_TYPE, ATTACK_START, ATTACK_END);

  simple_udp_register(&udp_conn, UDP_CLIENT_PORT,
                      NULL, UDP_SERVER_PORT,
                      udp_rx_callback);

  last_cpu = last_lpm = last_tx = last_rx = 0;
  last_app_tx = last_app_rx = 0;

  etimer_set(&app_timer, APP_INTERVAL);
  etimer_set(&log_timer, LOG_INTERVAL);

  while(1) {
    PROCESS_YIELD();

    if(etimer_expired(&app_timer)) {
      uip_ipaddr_t dest;
      if(NETSTACK_ROUTING.get_root_ipaddr(&dest)) {
        char msg[32];
        snprintf(msg, sizeof(msg), "Hello%u", node_id);
        simple_udp_sendto(&udp_conn, msg, strlen(msg), &dest);
        app_tx_count++;
      }
      etimer_reset(&app_timer);
    }

    if(etimer_expired(&log_timer)) {
      maybe_run_attack_logic();

      uint32_t now_s = clock_time() / CLOCK_SECOND;

      char my_ip[64];
      char parent_ip[64];
      char neighbors[256];

      get_ipv6_str(my_ip, sizeof(my_ip));
      get_parent_ipv6_str(parent_ip, sizeof(parent_ip));
      get_neighbor_list(neighbors, sizeof(neighbors));

      uint16_t rank = get_rpl_rank();
      int16_t rssi = get_rssi();
      double Ecpu, Elpm, Etx, Erx;
      get_energy(&Ecpu, &Elpm, &Etx, &Erx);
      float plr = get_plr_interval();

      printf(
        "DATA t=%lu id=%u atk=%d active=%d "
        "dio_rx=%lu dio_tx=%lu dao_rx=%lu dao_tx=%lu "
        "app_rx=%lu app_tx=%lu rank=%u "
        "parent=%s ip=%s neighbors=%s "
        "rssi=%d plr=%.4f "
        "Ecpu=%.6f Elpm=%.6f Etx=%.6f Erx=%.6f\n",
        (unsigned long)now_s,
        (unsigned)node_id,
        (int)ATTACK_TYPE,
        (int)is_attack_active(),
        (unsigned long)dio_rx_count,
        (unsigned long)dio_tx_count,
        (unsigned long)dao_rx_count,
        (unsigned long)dao_tx_count,
        (unsigned long)app_rx_count,
        (unsigned long)app_tx_count,
        (unsigned)rank,
        parent_ip,
        my_ip,
        neighbors,
        (int)rssi,
        (double)plr,
        Ecpu, Elpm, Etx, Erx
      );

      etimer_reset(&log_timer);
    }
  }

  PROCESS_END();
}
