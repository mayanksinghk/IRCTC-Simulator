# Architecture and Structural Diagrams

## 1) System intent

The simulator models a segmented ingress path and makes latency behavior explicit at each hop.

Why this exists:

- Separate **network zones** (edge, DMZ, management/app) for realistic pathing.
- Inject **per-hop delay distributions** from empirical/modelled data.
- Keep runtime and analysis decoupled, so PCAPs can be re-analyzed without rerunning Mininet.

---

## 2) Runtime topology (as implemented)

Reference: `Mininet/emulation.py` (`CRISDCNetwork.build` and `run`)

```mermaid
graph LR
  U[user1\n10.0.0.1/24]
  S1[s1]
  R[r1\n10.0.0.254 + 10.0.1.254]
  IPS[ips\n10.0.1.253 + 10.0.2.254]
  FW1[fw1\n10.0.2.253 + 10.0.3.254]
  S2[s2]
  ADC[adc1\n10.0.3.1]
  WAF[waf1\n10.0.3.2]
  WEB[web\n10.0.3.3]
  FW2[fw2\n10.0.3.253 + 10.0.4.254]
  S3[s3]
  SLB[slb1\n10.0.4.1]
  APP[app\n10.0.4.2]

  U --> S1 --> R --> IPS --> FW1 --> S2
  S2 --> ADC --> WAF --> WEB --> FW2 --> S3 --> SLB --> APP
```

---

## 3) Request/response path behavior

### TLS ingress path

```mermaid
sequenceDiagram
  participant User as user1
  participant IPS as ips_node.py
  participant ADC as adc_node.py
  participant WAF as waf_node.py
  participant WEB as web_node.py
  participant FW2 as fw2_node.py
  participant SLB as slb_node.py
  participant APPP as app_server_node.py
  participant APP as fast_app.py

  User->>IPS: HTTPS to 10.0.3.1:443
  IPS->>IPS: iptables REDIRECT intercept on 443
  IPS->>ADC: Forward TLS stream
  ADC->>ADC: TLS terminate + delay sample (optional)
  ADC->>WAF: Forward HTTP
  WAF->>WEB: Forward HTTP (+ optional delay)
  WEB->>FW2: Forward HTTP (+ optional delay)
  FW2->>SLB: Forward HTTP (+ optional delay)
  SLB->>APPP: Forward HTTP (pass-through)
  APPP->>APP: Forward to local backend 127.0.0.1:8080 (+ optional delay)
  APP-->>APPP: 200 OK
  APPP-->>SLB: response
  SLB-->>FW2: response
  FW2-->>WEB: response
  WEB-->>WAF: response
  WAF-->>ADC: response
  ADC-->>IPS: response
  IPS-->>User: HTTPS response
```

### Delay model usage

- Most nodes sample random values from `mininet_delays/*_delays.json` (`delays_seconds` array).
- SLB is intentionally pass-through (no added delay).
- `NO_DELAY_MODE=1` disables delay injection in node services.

---

## 4) Runtime orchestration pipeline

```mermaid
flowchart TD
  A[Run Mininet/emulation.py] --> B[Create topology and links]
  B --> C[Kernel tuning and static routes]
  C --> D[Disable IPv6 for hosts]
  D --> E[Start tcpdump on selected nodes]
  E --> F[Start backend and per-hop services]
  F --> G[Apply IPS iptables REDIRECT for 443 interception]
  G --> H[Launch traffic_gen.py from user1]
  H --> I[Observe/validate in Mininet CLI]
  I --> J[Exit CLI and stop network]
```

Captured nodes by default: `user1`, `ips`, `adc1`, `app`, `waf1`, `web`, `fw2`  
Capture filter: `tcp port 80 or tcp port 443`

---

## 5) Offline analysis architecture

```mermaid
flowchart LR
  P[PCAP inputs] --> H1[HTTP analyzers]
  P --> T1[TLS analyzers]
  P --> S1[Sockets analyzers]
  P --> A1[ASN enrichment]
  P --> G1[GMM delay-model pipeline]

  H1 --> O1[HTTP RTT CSV + method-specific plots]
  T1 --> O2[TLS CSV + RTT distributions]
  S1 --> O3[unique IP/socket/biflow + protocol markdown]
  A1 --> O4[IP-to-ASN CSV + Excel outputs]
  G1 --> O5[delay model files for Mininet]
```

---

## 6) Design decisions and tradeoffs

- **Chained application proxies** make hop-by-hop effects measurable and debuggable.
- **Generated delay pools** are simple to sample at runtime and avoid expensive per-request model inference.
- **Standalone analysis scripts** make ad-hoc forensic runs easy, but dependency management is manual.
- **Scenario IDs** (`3`, `5`, `6-7`, `8-9`, `10`, `11`, `12`) support comparative experiments but rely on naming conventions in shell scripts.
