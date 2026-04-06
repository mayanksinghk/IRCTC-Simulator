# File-by-File Guide (what happens where, and why)

This guide focuses on behavior-driving files and practical ownership boundaries.

---

## A) Runtime orchestration (`Mininet/`)

| File | What it does now | Why it matters |
|---|---|---|
| `Mininet/emulation.py` | Creates topology, tunes kernel/network, installs static routes, starts tcpdump, launches all node services, starts load generation, and handles teardown. | Main entrypoint for end-to-end simulation. |
| `Mininet/traffic_gen.py` | Async HTTPS load generator (`aiohttp`) aimed at `https://10.0.3.1/` with configurable request volume/concurrency in source. | Produces controlled high-throughput traffic through full chain. |
| `Mininet/topology.py` | Older interactive topology workflow using terminal windows (`makeTerm`) and manual service startup. | Useful for manual debugging but secondary to `emulation.py`. |
| `Mininet/delay_proxy.py` | Generic delay-aware forwarding helper (not the primary node path in current orchestration). | Reference/utility implementation for latency injection concepts. |
| `Mininet/compare_gmm.py` | GMM comparison helper used during model analysis workflows. | Supports delay-model validation work. |
| `Mininet/Post_Simulation/full_gmm.py` | Post-simulation modeling utility for fitting delay distributions and reporting. | Delay model generation/inspection path tied to experiments. |

---

## B) Node services (`Mininet/Servers/`)

| File | Role in request path | Delay profile used |
|---|---|---|
| `Mininet/Servers/ips_node.py` | Transparent interception listener (port 443), forwards TLS stream to ADC; can inject delay on response side. | `mininet_delays/ips_delays.json` |
| `Mininet/Servers/adc_node.py` | TLS termination edge, forwards HTTP to WAF. | `mininet_delays/adc_delays.json` |
| `Mininet/Servers/waf_node.py` | HTTP proxy WAF hop, forwards to Web. | `mininet_delays/waf_delays.json` |
| `Mininet/Servers/web_node.py` | HTTP proxy web tier, forwards to FW2. | `mininet_delays/web_server_delays.json` |
| `Mininet/Servers/fw2_node.py` | Backend firewall hop, forwards to SLB. | `mininet_delays/backend_firewall_delays.json` |
| `Mininet/Servers/slb_node.py` | Pass-through load-balancer hop forwarding to app node. | No explicit delay injection |
| `Mininet/Servers/app_server_node.py` | App proxy layer forwarding to local backend logic on `127.0.0.1:8080`. | `mininet_delays/application_server_delays.json` |
| `Mininet/Servers/fast_app.py` | Final backend business endpoint returning quick success response. | N/A |

Support assets:

- `Mininet/Servers/SSL_Keys/adc_cert.pem`, `adc_key.pem` (ADC TLS)
- `Mininet/Servers/mininet_delays/` (JSON delay pools and reports)

---

## C) Delay model / preprocessing pipeline (`PCAP/Code/`)

| File | What it does | Output |
|---|---|---|
| `PCAP/Code/full_gmm.py` | Filters PCAP traffic by mode (TLS/HTTP), extracts delay metadata, fits Gaussian Mixture Models, saves model + plots. | `*_model_mode*.pkl`, latency CSV, distribution/component plots |
| `PCAP/Code/generate_mininet_delays.py` | Samples from fitted models (and optional subtraction) to produce runtime delay pools. | JSON with `delays_seconds` |
| `PCAP/Code/analyze_node_math.py` | Analysis helper for node-level math/reporting. | Node analysis artifacts |
| `PCAP/Code/verify.py` | Utility verification script for intermediate outputs. | Validation output |
| `PCAP/Code/run_analysis.sh` | Batch runner for standard scenario captures and modes. | Per-scenario modeling outputs |

---

## D) HTTP analysis (`PCAP/http/`)

| File | What it does | Typical output |
|---|---|---|
| `PCAP/http/http_extract.py` | Extracts request/response HTTP lines and summary-friendly data from PCAP. | Text/CSV summaries |
| `PCAP/http/get.py` | Groups normalized GET APIs using IRCTC-specific URI normalization. | GET frequency CSV |
| `PCAP/http/post.py` | Groups normalized POST APIs with same normalization strategy. | POST frequency CSV |
| `PCAP/http/unique_http.py` | Broad HTTP fingerprint extraction pipeline. | Unique endpoint/feature outputs |
| `PCAP/http/RTT/http_rtt.py` | Matches request/response pairs and computes RTT with relative timestamps. | `<scenario>_http_rtt.csv` |
| `PCAP/http/RTT/rtt.py` | Produces RTT distribution plots (all/GET/POST) from RTT CSV. | PNG distributions |
| `PCAP/http/RTT/run.sh` | Batch runner for scenario PCAPs (`8-9`, `10`, `11`, `12`). | Per-scenario RTT folders |
| `PCAP/http/graph.py` | Additional plotting utility for RTT-style CSV data. | Graph PNGs |

---

## E) TLS analysis (`PCAP/tls/`)

| File | What it does | Typical output |
|---|---|---|
| `PCAP/tls/tls_rtt.py` | Parses true TLS records from PCAP and writes time/src/dst/ports/length CSV. | TLS extracted CSV |
| `PCAP/tls/rtt.py` | Computes RTT (server-subnet aware), writes RTT CSV and RTT plots. | RTT CSV + dist/counter PNGs |
| `PCAP/tls/length_distribution.py` | Payload length distribution plotting helper. | Distribution plots |
| `PCAP/tls/run.sh` | Batch script: tshark TLS filtering + extraction + RTT plots for scenario set (`3`, `5`, `6-7`). | Per-scenario folders |

---

## F) Socket/IP/port analysis (`PCAP/Sockets/`)

| File | What it does | Typical output |
|---|---|---|
| `PCAP/Sockets/sockets.py` | Parallel extraction of unique IPs, sockets, normalized biflows from PCAP. | `*_unique_ips.txt`, `*_unique_sockets.txt`, `*_unique_biflows.txt` |
| `PCAP/Sockets/port.py` | Maps observed ports to protocol names and enriches with ASN mapping CSV. | Markdown protocol summaries |
| `PCAP/Sockets/Port/port1.py` | Port classification helper used in socket reporting workflows. | Port-organized outputs |
| `PCAP/Sockets/Port/run.sh` | Batch runner invoking `port.py` per standard scenario IDs. | `Port/<scenario>.md` style outputs |
| `PCAP/Sockets/Subnets/subnet.py` | Subnet-based filtering of extracted socket/IP data. | Subnet-specific files |

---

## G) ASN enrichment (`PCAP/ASN/`)

| File | What it does | Typical output |
|---|---|---|
| `PCAP/ASN/ASN.py` | Loads public IPv4s, resolves ASN via MaxMind, builds prefix tree (PyTricia), exports summary artifacts. | `asn_lookup.xlsx`, `*_matched_ips.csv`, `unmatched_ips.txt` |

---

## H) Scenario and output conventions

- Scenario labels in scripts: `3`, `5`, `6-7`, `8-9`, `10`, `11`, `12`
- Batch scripts usually assume inputs under `Data/Input_PCAP/`
- Generated results commonly live under protocol folders and per-scenario subdirectories

---

## I) Legacy or historical areas

- `PCAP/http/old/` — previous HTTP analysis iterations
- `PCAP/tls/Old/` — older TLS outputs/pipeline traces
- `PCAP/http/HTTP packets uri/` — historical exploratory outputs/scripts

Treat these as reference/history unless a workflow explicitly points to them.
