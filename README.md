# IRCTC-Simulator

This repository simulates an IRCTC-like multi-layer network path in Mininet and then analyzes captured traffic (HTTP/TLS/socket/ASN/RTT) from generated PCAPs.

It is split into two major parts:

- `Mininet/` → emulation runtime (topology, delay-proxy chain, load generation)
- `PCAP/` → offline traffic analysis and reporting pipelines

## Documentation Index

- [Architecture and Structural Diagrams](docs/ARCHITECTURE.md)
- [File-by-File Guide (what happens where and why)](docs/FILE_GUIDE.md)
- [Execution and Analysis Workflows](docs/WORKFLOWS.md)

## High-Level Flow

1. Build and start a Mininet topology representing user → border devices → DMZ → app tier.
2. Run chained delay-aware proxies to emulate observed latency distributions.
3. Generate HTTPS load from the user node.
4. Capture traffic from selected nodes as PCAP.
5. Run protocol-specific analyzers in `PCAP/` to produce summaries, CSVs, plots, and reports.

## Main Runtime Entry

- `Mininet/emulation.py`

## Analysis Families

- `PCAP/http/` → HTTP extraction, API grouping, HTTP RTT analysis
- `PCAP/tls/` → TLS packet extraction and RTT analysis
- `PCAP/Sockets/` → unique IPs/sockets/biflows and port-based summaries
- `PCAP/ASN/` → ASN enrichment and prefix mapping
- `PCAP/NetworkTime/` → TCP RTT extraction and plotting

## Notes

- This repo currently has no root build/test automation file (`Makefile`, `pyproject.toml`, `requirements.txt`) checked in.
- Most scripts are standalone CLI tools using `argparse`.
