# Secure-Routing-IoT
# Mobility-Aware Trust-Based Secure Routing for RPL-Based IoT Networks

This repository provides the implementation and experimental resources for a **mobility-aware, trust-based routing framework** designed to enhance the security and stability of RPL-based Internet of Things (IoT) networks operating under highly dynamic conditions.

The project is developed as part of an **academic research study and  scientific paper**, with the aim of improving trust management and secure routing in  mobile IoT environments.



## Overview

IoT networks deployed in mobile and urban environments experience rapidly changing topologies, intermittent connectivity, and heterogeneous node behaviors. Under such conditions, even authenticated nodes can launch stealthy routing attacks that bypass conventional cryptographic protections, threatening network reliability and data integrity.

To address these challenges, this work proposes a **temporal–spatial trust framework** that models the IoT network as a continuously evolving dynamic graph. Node behaviors are represented as temporal sequences enriched with neighborhood-level contextual features derived from mobility, traffic, and structural characteristics.

These sequences are processed using a ** GRU-based Sequence-to-Sequence (Seq2Seq) architecture with multi-head attention**, enabling the model to capture both short-term temporal dynamics and long-range spatial dependencies.

---


## Experimental Setup

- **Simulation Platform:** Contiki-NG  
- **Routing Protocol:** RPL  
- **Mobility Data:** Microsoft GeoLife real-world trajectory dataset  
- **Attack Scenarios:** Rank, Blackhole, Sinkhole, Selective Forwarding, Sybil attacks  
- **Network Conditions:** Static and Mobility environments  

---

## Purpose and Usage

This repository is created to:

- Support **reproducibility** of the results reported in the associated research paper  
- Provide a **reference implementation** for researchers studying secure routing and trust management in IoT networks  
- Enable further experimentation and extension of mobility-aware security mechanisms  

This code is provided for **research and academic use only**.

---

## Authors

- Zohre Shoaei, Dr.Rasool Esmaeilyfard*, Dr.Reza Javidan  
- Department of Computer and Information Technology Engineering, Shiraz University of Technology

---

## Citation

If you use this work in your research, please cite the corresponding paper:




## Repository Structure

