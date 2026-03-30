# File-by-File Guide (What happens where, and why)

This guide focuses on the files that drive behavior. Generated result artifacts are not exhaustively listed.

## A) Mininet Runtime (`Mininet/`)

| File | What happens in this file | Why it exists |
|---|---|---|
| `Mininet/emulation.py` | Builds topology, assigns IPs/routes, starts packet capture, launches proxy chain, launches load generator, handles cleanup. | Main orchestrator for full end-to-end emulation experiment. |
| `Mininet/topology.py` | Alternative/manual topology runner with CLI terminals and explicit service startup order. | Useful for interactive debugging/stepwise validation of path. |
| `Mininet/delay_proxy.py` | Async reverse proxy that applies sampled delay from CSV/PCAP-derived distributions, then forwards traffic. Optional TLS on listener. | Core mechanism for realistic per-hop latency emulation. |
| `Mininet/fast_app.py` | Lightweight aiohttp backend on port 8080 returning immediate success. | Stable backend target for high-throughput load tests. |
| `Mininet/traffic_gen.py` | Async concurrent HTTPS load generator (`aiohttp`) with queue workers and summary metrics. | Reproducible load injection for latency/capacity experiments. |

## B) Service Implementations (`Mininet/Servers/`)

| File | What happens in this file | Why it exists |
|---|---|---|
| `Mininet/Servers/adc.py` | TLS edge listener (443), client ID tagging, forwards to WAF connection pool. | Models ADC/TLS-termination role at DMZ edge. |
| `Mininet/Servers/waf.py` | Receives framed messages, maintains backend pool, forwards to backend and routes responses back by client ID. | Models WAF/inspection hop and stateful response routing. |
| `Mininet/Servers/web.py` | Length-prefixed TCP backend service, returns `ACK` payload tied to client ID. | Represents web/application processing hop for chain testing. |
| `Mininet/Servers/app.py` | Minimal HTTP server returning success message on port 80. | Simple endpoint when validating proxy-chain traversal. |
| `Mininet/Servers/user.py` | Interactive TLS client for manual handshake/message testing against ADC. | Manual protocol testing and quick smoke checks. |
| `Mininet/Servers/delay_proxy.py` | Same delay-proxy concept mirrored under `Servers/`. | Co-located helper for service-side experiments. |
| `Mininet/Servers/1temp.py` | Experimental ADC/WAF integration prototype retained for debugging reference. | Preserves an earlier design path; recommended future rename to `adc_experimental.py` if maintained long-term. |

## C) HTTP Analysis (`PCAP/http/`)

| File | What happens in this file | Why it exists |
|---|---|---|
| `PCAP/http/http_extract.py` | Parallel extraction of HTTP request/response lines from PCAP with summaries. | Builds normalized plain-text datasets from raw capture. |
| `PCAP/http/get.py` | Parallel grouping/count of GET URIs with IRCTC-specific URI normalization. | Quantifies GET API usage patterns across captures. |
| `PCAP/http/post.py` | Parallel grouping/count of POST URIs with same normalization strategy. | Quantifies POST API usage patterns consistently. |
| `PCAP/http/unique_http.py` | Broad HTTP fingerprinting pipeline (streaming + parallel). | Larger-scale endpoint/feature extraction from traffic. |
| `PCAP/http/RTT/http_rtt.py` | Matches request→response pairs and writes per-request RTT CSV with relative timestamps. | Canonical RTT dataset generator for HTTP. |
| `PCAP/http/RTT/rtt.py` | Consumes RTT CSV and produces summaries/plots for GET/POST/all methods. | Converts RTT data into interpretable metrics/charts. |
| `PCAP/http/graph.py` | Plots RTT distributions and RTT-vs-index graphs from CSV. | Quick visualization utility for RTT behavior. |

## D) TLS Analysis (`PCAP/tls/`)

| File | What happens in this file | Why it exists |
|---|---|---|
| `PCAP/tls/tls_rtt.py` | Parallel TLS record extraction (length, src/dst/ports, relative time) into CSV. | Structured TLS-level dataset generation from PCAP. |
| `PCAP/tls/rtt.py` | Computes/plots TLS RTT distributions and packet counters. | Performance characterization at TLS record layer. |
| `PCAP/tls/length_distribution.py` | Length distribution plotting helpers. | Payload-size behavior analysis. |
| `PCAP/tls/run.sh` | Batch helper script for TLS analysis runs. | Convenience execution wrapper for repeated jobs. |

## E) Socket / IP / Port Analysis (`PCAP/Sockets/`)

| File | What happens in this file | Why it exists |
|---|---|---|
| `PCAP/Sockets/sockets.py` | Parallel extraction of unique IPs, unique sockets, and normalized biflows. | Base network connectivity inventory from captures. |
| `PCAP/Sockets/port.py` | Converts socket/IP/ASN data into markdown protocol summaries. | Human-readable reporting layer for socket data. |
| `PCAP/Sockets/Port/port1.py` | Port classification and protocol folder generation. | Organizes outputs by protocol/port semantics. |
| `PCAP/Sockets/Subnets/subnet.py` | Filters IP/socket sets by configured subnet groups. | Separates private/CRIS/public views for analysis. |
| `PCAP/Sockets/Subnets/subnet.sh` | Shell wrapper around subnet filtering pipeline. | Fast repeatable execution for subnet reports. |

## F) RTT / Network Time (`PCAP/NetworkTime/`)

| File | What happens in this file | Why it exists |
|---|---|---|
| `PCAP/NetworkTime/tcp_rtt.py` | Extracts TCP RTT by matching payload seq ranges with reverse ACKs. | TCP-layer latency baseline independent of HTTP parsing. |
| `PCAP/NetworkTime/plot.py` | Produces interactive RTT distributions/statistics. | Visual analysis for RTT text outputs. |
| `PCAP/NetworkTime/tshark_command.py` | Builds tshark filter command using IP list. | Reproducible pre-filtering and extraction commands. |

## G) ASN Enrichment (`PCAP/ASN/`)

| File | What happens in this file | Why it exists |
|---|---|---|
| `PCAP/ASN/ASN.py` | Extracts public IPs, looks up ASN via MaxMind, builds prefix mapping (PyTricia), exports Excel/CSV summaries. | Converts raw public IP observations into organizational/network ownership context. |

## H) Generated Outputs and Scenario Buckets

- Folders such as `PCAP/Final/`, `PCAP/http/RTT/<scenario>/`, `PCAP/tls/<scenario>/`, `PCAP/Sockets/Output/<scenario>/` contain generated experiment outputs.
- Scenario labels (`3`, `5`, `6-7`, `8-9`, `10`, `11`, `12`) represent different run/capture batches.

## I) Legacy/Experimental Areas

- `Mininet/old/` and `PCAP/http/old/` contain older iterations kept for reference.
- They are useful for historical comparison but not the primary current path.
