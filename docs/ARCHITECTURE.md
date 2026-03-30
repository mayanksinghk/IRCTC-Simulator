# Architecture and Structural Diagrams

## 1) System Context

The simulator models a layered ingress path similar to production network segmentation:

- External user traffic enters through edge/border controls.
- Traffic traverses DMZ controls (ADC/WAF/Web layer).
- Requests are forwarded to management/application tier.
- Delay profiles are injected per hop to emulate realistic latency behavior.

## 2) Topology Structure (Mininet)

```mermaid
graph LR
  U[user1\n10.0.0.1/24]
  S1[s1 / ISP switch]
  R[r1\n10.0.0.254 + 10.0.1.254]
  IPS[ips\n10.0.1.253 + 10.0.2.254]
  FW1[fw1\n10.0.2.253 + 10.0.3.254]
  S2[s2 / DMZ switch]
  ADC[adc1\n10.0.3.1]
  WAF[waf1\n10.0.3.2]
  WEB[web\n10.0.3.3]
  FW2[fw2\n10.0.3.253 + 10.0.4.254]
  S3[s3 / MZ switch]
  SLB[slb1\n10.0.4.1]
  APP[app\n10.0.4.2]

  U --> S1 --> R --> IPS --> FW1 --> S2
  S2 --> ADC --> WAF --> WEB --> FW2 --> S3 --> SLB --> APP
```

Reference implementation: `Mininet/emulation.py` (`CRISDCNetwork.build`).

## 3) Request Path Sequence (TLS edge)

```mermaid
sequenceDiagram
  participant User as user1
  participant IPS as ips proxy
  participant ADC as adc1 proxy (TLS terminate)
  participant WAF as waf1 proxy
  participant WEB as web proxy
  participant FW2 as fw2 proxy
  participant SLB as slb1 proxy
  participant APP as app backend

  User->>IPS: HTTPS request
  IPS->>ADC: forward
  ADC->>ADC: TLS decrypt + optional delay profile
  ADC->>WAF: HTTP forward
  WAF->>WEB: forward
  WEB->>FW2: forward
  FW2->>SLB: forward
  SLB->>APP: forward to backend app
  APP-->>SLB: response
  SLB-->>FW2: response
  FW2-->>WEB: response
  WEB-->>WAF: response
  WAF-->>ADC: response
  ADC-->>IPS: response
  IPS-->>User: HTTPS response
```

## 4) Runtime Pipeline (emulation side)

```mermaid
flowchart TD
  A[Start Mininet/emulation.py] --> B[Build topology + links]
  B --> C[Assign interface IPs + static routes]
  C --> D[Enable forwarding + disable IPv6]
  D --> E[Start tcpdump on selected nodes]
  E --> F[Start backend app]
  F --> G[Start delay proxies hop-by-hop]
  G --> H[Start load generator from user1]
  H --> I[Interactive CLI for validation]
  I --> J[Cleanup background processes]
  J --> K[PCAP files ready for offline analysis]
```

## 5) Offline Analysis Pipeline (PCAP side)

```mermaid
flowchart LR
  P[PCAP inputs] --> H1[HTTP analyzers\nhttp_extract/get/post/http_rtt]
  P --> T1[TLS analyzers\ntls_rtt/rtt]
  P --> S1[Sockets analyzers\nsockets/port/subnet]
  P --> N1[NetworkTime analyzers\ntcp_rtt/plot]
  P --> A1[ASN enrichment\nASN.py]

  H1 --> O1[CSV + summaries + RTT graphs]
  T1 --> O2[TLS CSV + distributions]
  S1 --> O3[unique IP/socket/biflow files + markdown]
  N1 --> O4[RTT text + plots]
  A1 --> O5[Excel/CSV ASN mappings]
```

## 6) Why this structure exists

- **Layered path**: separates edge, DMZ, and app zones for realistic security/perimeter behavior.
- **Delay profiles per hop**: allows replaying empirical latency distributions rather than fixed sleeps.
- **Standalone analyzers**: each script focuses on one protocol outcome, making post-capture analysis composable.
- **Generated outputs versioned by scenario IDs** (e.g., `3`, `5`, `6-7`, `8-9`, etc.): supports comparative experiments.
