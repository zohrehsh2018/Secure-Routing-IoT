#!/usr/bin/env python3
import os
import re
import csv

LOG_FILE = os.environ.get("DATASET_LOG_FILE", "sim_log.txt")
OUT_FILE = os.environ.get("DATASET_OUT_FILE", "dataset.csv")

R = re.compile(
    r"DATA t=(\d+) id=(\d+) atk=(\d+) active=(\d+) "
    r"dio_rx=(\d+) dio_tx=(\d+) dao_rx=(\d+) dao_tx=(\d+) "
    r"app_rx=(\d+) app_tx=(\d+) rank=(\d+) "
    r"parent=([^ ]+) ip=([^ ]+) neighbors=([^ ]+) "
    r"rssi=(-?\d+) plr=([0-9.]+) "
    r"Ecpu=([0-9.]+) Elpm=([0-9.]+) Etx=([0-9.]+) Erx=([0-9.]+)"
)

def parse_log(path):
  rows = []
  with open(path, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
      m = R.search(line)
      if not m:
        continue
      g = m.groups()
      rows.append({
          "time": int(g[0]),
          "node_id": int(g[1]),
          "attack_type": int(g[2]),
          "attack_active": int(g[3]),
          "dio_rx": int(g[4]),
          "dio_tx": int(g[5]),
          "dao_rx": int(g[6]),
          "dao_tx": int(g[7]),
          "app_rx": int(g[8]),
          "app_tx": int(g[9]),
          "rank": int(g[10]),
          "parent": g[11],
          "ipv6": g[12],
          "neighbors": g[13],
          "rssi": int(g[14]),
          "plr": float(g[15]),
          "Ecpu": float(g[16]),
          "Elpm": float(g[17]),
          "Etx": float(g[18]),
          "Erx": float(g[19]),
      })
  return rows

def write_dataset(rows, path):
  if not rows:
    print("No DATA lines found in log:", LOG_FILE)
    return

  fieldnames = list(rows[0].keys())
  with open(path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for r in rows:
      w.writerow(r)
  print("Wrote dataset:", path, "rows=", len(rows))

def main():
  print("Parsing log:", LOG_FILE)
  rows = parse_log(LOG_FILE)
  write_dataset(rows, OUT_FILE)

if __name__ == "__main__":
  main()
