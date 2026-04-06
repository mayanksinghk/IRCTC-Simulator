# Execution and Analysis Workflows

This document is the practical “what to run, in what order, and why.”

---

## 1) End-to-end emulation workflow

```mermaid
flowchart TD
  A[Run Mininet/emulation.py] --> B[Build topology and links]
  B --> C[Apply kernel tuning and static routes]
  C --> D[Disable IPv6 and set default routes]
  D --> E[Start tcpdump captures]
  E --> F[Launch backend and node services]
  F --> G[Apply IPS PREROUTING redirect for 443]
  G --> H[Launch traffic generator from user1]
  H --> I[Inspect/validate in Mininet CLI]
  I --> J[Exit CLI and cleanup]
```

### What you need before running

- Mininet + OVS + Linux networking tools (`tcpdump`, `iptables`, `ethtool`)
- Python environment with runtime packages used by node services
- ADC TLS cert/key in `Mininet/Servers/SSL_Keys/`
- Delay pool JSON files under `Mininet/Servers/mininet_delays/`

### Run

```bash
cd Mininet
sudo python3 emulation.py
```

Generated captures are written to `Mininet/PCAP/`.

---

## 2) Delay model generation workflow (for Mininet delay pools)

```mermaid
flowchart LR
  P[Input PCAP] --> F[PCAP/Code/full_gmm.py]
  F --> M[Per-scenario model .pkl]
  M --> G[generate_mininet_delays.py]
  G --> D[mininet_delays/*.json]
  D --> R[Consumed by Mininet/Servers/*_node.py]
```

Batch helper for standard scenarios:

```bash
cd PCAP/Code
bash run_analysis.sh
```

---

## 3) HTTP analysis workflow

```mermaid
flowchart LR
  P[Input pcap] --> H1[http_extract.py]
  P --> H2[get.py / post.py]
  P --> H3[RTT/http_rtt.py]
  H3 --> H4[RTT/rtt.py]
  H2 --> O1[Normalized API frequency CSV]
  H4 --> O2[RTT plots by method]
```

Batch RTT path used in repo:

```bash
cd PCAP/http/RTT
bash run.sh
```

Default script assumes `Data/Input_PCAP/{8-9,10,11,12}.pcap`.

---

## 4) TLS analysis workflow

```mermaid
flowchart LR
  P[Input pcap] --> T0[tshark filter in run.sh]
  T0 --> T1[tls_rtt.py]
  T1 --> T2[rtt.py]
  T2 --> O[TLS RTT CSV + distribution/counter plots]
```

Batch run:

```bash
cd PCAP/tls
bash run.sh
```

Notes:

- `run.sh` filters traffic with a subnet-specific TLS filter expression.
- Scenario defaults are `3`, `5`, and `6-7`.

---

## 5) Sockets + ASN workflow

```mermaid
flowchart LR
  P[Input pcap] --> S1[sockets.py]
  S1 --> S2[port.py]
  S1 --> A1[ASN.py]
  A1 --> S2
  S2 --> O1[Protocol markdown summaries]
  A1 --> O2[IP-to-ASN CSV + Excel]
```

Typical sequence:

1. Generate unique IP/socket/biflow lists with `sockets.py`
2. Build ASN map with `ASN.py`
3. Generate per-protocol markdown summaries with `port.py` (or `Port/run.sh`)

---

## 6) Operational caveats to know

- `Mininet/emulation.py` contains absolute machine-specific paths for Python/script dir; update these on new setups.
- Batch scripts rely on scenario-named inputs in `Data/Input_PCAP/`.
- Some analysis choices are intentionally environment-specific (for example TLS subnet filter in `PCAP/tls/run.sh`).
- Runtime captures only include TCP 80/443 by default.

---

## 7) Why workflows are split

- Emulation requires privileged networking/runtime dependencies.
- Analysis can run independently on existing PCAP archives.
- Protocol-specific scripts keep outputs small, targeted, and easier to validate.
