# Execution and Analysis Workflows

## 1) End-to-End Emulation Workflow

```mermaid
flowchart TD
  A[Run Mininet/emulation.py] --> B[Topology + addressing + routes]
  B --> C[Enable forwarding and baseline sysctl]
  C --> D[Start tcpdump captures]
  D --> E[Start app backend]
  E --> F[Start delay proxies in chain order]
  F --> G[Run user load generator]
  G --> H[Inspect from Mininet CLI]
  H --> I[Stop and cleanup]
  I --> J[Use generated PCAP files for offline analysis]
```

### Practical behavior

- `emulation.py` hard-codes a startup order because each hop depends on next-hop availability.
- Delay profile files under `Mininet_Profiles/` are consumed by `delay_proxy.py`.
- TLS is terminated at ADC edge (configured with cert/key), then forwarded internally.

## 2) HTTP Analysis Workflow

```mermaid
flowchart LR
  P[Input pcap] --> E1[http_extract.py]
  E1 --> E2[get.py / post.py]
  E1 --> E3[RTT/http_rtt.py]
  E3 --> E4[RTT/rtt.py or graph.py]
  E2 --> O1[URI frequency CSV]
  E4 --> O2[RTT distributions + summary plots]
```

## 3) TLS Analysis Workflow

```mermaid
flowchart LR
  P[Input pcap] --> T1[tls_rtt.py]
  T1 --> T2[rtt.py]
  T2 --> O[TLS RTT graphs + distributions]
```

## 4) Socket + ASN Workflow

```mermaid
flowchart LR
  P[Input pcap] --> S1[sockets.py]
  S1 --> S2[subnet.py / port.py]
  S1 --> A1[ASN.py]
  S2 --> O1[IP/socket/biflow markdown + txt]
  A1 --> O2[ASN excel/csv mappings]
```

## 5) File/Folder Intent at a Glance

- **Runtime code**: `Mininet/`
- **Runtime services**: `Mininet/Servers/`
- **Captured artifacts**: `PCAP/...` scenario folders
- **Offline analyzers**: `PCAP/*/*.py`

## 6) Why these workflows are separated

- Emulation and analysis have different compute/runtime dependencies.
- Analysts can rerun parsing scripts on existing PCAPs without rerunning Mininet.
- Per-protocol scripts keep outputs modular and easier to validate.
