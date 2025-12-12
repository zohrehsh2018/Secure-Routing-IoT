# Secure-Routing-IoT
# Mobility-Aware Trust-Based Secure Routing for RPL-Based IoT Networks

This repository provides the full implementation and experimental resources for a **mobility-aware, trust-based routing framework** designed to enhance the security and stability of RPL-based Internet of Things (IoT) networks operating under highly dynamic conditions.

The project is developed as part of an **academic research study and accompanying scientific paper**, with the aim of improving trust management and secure routing in next-generation mobile IoT environments.

---

## Overview

IoT networks deployed in mobile and urban environments experience rapidly changing topologies, intermittent connectivity, and heterogeneous node behaviors. Under such conditions, even authenticated nodes can launch stealthy routing attacks that bypass conventional cryptographic protections, threatening network reliability and data integrity.

To address these challenges, this work proposes a **temporal–spatial trust framework** that models the IoT network as a continuously evolving dynamic graph. Node behaviors are represented as temporal sequences enriched with neighborhood-level contextual features derived from mobility, traffic, and structural characteristics.

These sequences are processed using a **multi-layer GRU-based Sequence-to-Sequence (Seq2Seq) architecture with multi-head attention**, enabling the model to capture both short-term temporal dynamics and long-range spatial dependencies.

---

## Trust Framework Design

The proposed framework integrates multiple trust evidence sources to compute a robust and adaptive trust score for each node:

- **Model-inferred behavioral anomalies** obtained from sequence prediction errors  
- **Deterministic protocol-level checks** derived from routing and control message behavior  
- **Peer-reported reputation** aggregated from neighboring nodes  

A weighted fusion mechanism, optimized through hyperparameter tuning, combines these trust signals. The resulting trust scores are embedded into **RPL’s rank computation** and regulated using a **hysteresis-based parent selection policy**, ensuring fast isolation of malicious nodes while preserving routing stability.

---

## Experimental Setup

- **Simulation Platform:** Contiki-NG  
- **Routing Protocol:** RPL  
- **Mobility Data:** Microsoft GeoLife real-world trajectory dataset  
- **Attack Scenarios:** Five distinct routing and forwarding attacks  
- **Network Conditions:** Static, low-mobility, and highly dynamic environments  

---

## Key Results

The proposed approach demonstrates strong performance across diverse scenarios:

- Up to **96% detection accuracy** for covert forwarding and routing attacks  
- **38% reduction in attack detection latency**  
- **20–40% reduction in control-message overhead** compared to baseline methods  
- Runtime memory footprint maintained under **10 KB**, suitable for resource-constrained IoT devices  

The framework remains effective under both static and highly dynamic network conditions.

---

## Repository Structure

