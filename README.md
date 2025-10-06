# IRCTC-Simulator

# IRCTC-Simulator

This repository simulates a simple client-proxy-server architecture, useful for experimenting with network traffic, proxies, and TLS payload analysis. The codebase is organized into several Python scripts and supporting files.

## Network Diagram

Below is a simple network diagram showing how the components interact:

```
┌────────┐      8000        9000       ┌────────┐
│ Client ├─────────▶ Proxy ├──────────▶│ Server │
└────────┘◀────────┤       ├◀─────────┤        │
     │         └────────┘          └────────┘
     │
     │  (User types messages)      (Echoes back)
     ▼
   [start_proxy.sh launches all three]
```

**Flow:**

- The client connects to the proxy on port 8000.
- The proxy forwards all data to the server on port 9000.
- The server echoes responses back through the proxy to the client.

---

## Overview

The main components are:

- **server.py**: A basic TCP echo server. It listens for incoming connections, receives messages from clients, and sends back an "Echo: ..." response.
- **proxy.py**: A TCP proxy that sits between the client and the server. It forwards data in both directions, allowing you to observe or manipulate traffic between the client and server.
- **client.py**: A simple TCP client that connects to the proxy, sends user-input messages, and displays responses from the server.
- **start_proxy.sh**: A shell script to launch the server, proxy, and client in separate terminal windows for easy testing.
- **Capture_payload_tls.py**: A utility script to estimate application-layer payload sizes from a TLS-encrypted pcap file. It analyzes the capture and outputs a CSV with per-stream statistics.

### Directory Structure & Advanced Simulations

#### Mininet/

This directory contains scripts for simulating a realistic, multi-layered data center network using [Mininet](http://mininet.org/). It includes:

- **topology.py**: Defines a complex network topology with routers, firewalls, DMZ, ADC (Application Delivery Controller), WAF (Web Application Firewall), web server, and load balancer. It uses Mininet to create virtual hosts and switches, sets up static routes, and launches server scripts in terminals for each network function.
- **Servers/**: Contains the actual server scripts and certificates for each network function:
  - **adc.py**: A TLS-terminating proxy (ADC) that accepts HTTPS connections, decrypts them, and forwards traffic to the WAF.
  - **waf.py**: The Web Application Firewall, which receives HTTP traffic from the ADC and forwards it to the web server, logging and potentially filtering requests.
  - **web.py**: The web server, which responds to HTTP requests with a simple message.
  - **user.py**: Simulates a user client that generates random HTTP requests over TLS to the ADC.
  - **adc.crt/key**: TLS certificate and key for the ADC.

**How it fits:**
The Mininet setup allows you to experiment with a realistic, multi-tiered network, including security appliances and encrypted traffic, all on a single machine. You can observe how traffic flows through each layer and test security or routing policies.

#### My_Simulator/

This directory provides a modular, script-based simulation of a secure web application environment, without Mininet. It includes:

- **adc.py**: A TLS proxy (ADC) similar to the Mininet version, handling encrypted client connections and forwarding to the WAF.
- **web_server.py**: A web server that responds to requests from the WAF.
- **app_server.py**: An application server that the web server communicates with, simulating a backend service.
- **client.py**: A TLS client that connects to the ADC, sends messages, and displays responses.
- **run.sh**: A shell script to launch the components in the correct order.
- **adc.crt/key**: TLS certificate and key for the ADC.

**How it fits:**
This setup is ideal for testing secure proxying, backend communication, and TLS interception in a simpler, script-driven environment. It is useful for debugging, development, or running on systems where Mininet is not available.

---

## How It Works

1. **Server** (`server.py`):

    - Listens on port 9000 by default.
    - For each client connection, starts a new thread to handle communication.
    - Echoes back any received message with an "Echo: " prefix.

2. **Proxy** (`proxy.py`):

    - Listens on port 8000 by default.
    - Forwards all data between the client and the server (on port 9000).
    - Runs two threads per connection to handle bidirectional data transfer.

3. **Client** (`client.py`):

    - Connects to the proxy (port 8000).
    - Reads user input, sends it to the server via the proxy, and prints the server's response.

4. **start_proxy.sh**:

    - Launches the server, proxy, and client in separate GNOME terminal windows for convenience.

5. **Capture_payload_tls.py**:

    - Analyzes a TLS-encrypted pcap file to estimate the size of the original application payloads.
    - Outputs a CSV file with per-stream statistics, including estimated plaintext bytes and cipher suite information.

## Usage

1. **Start the system**:
    - Run `./start_proxy.sh` (requires GNOME Terminal and Python 3).
    - This will open three terminals: one each for the server, proxy, and client.

2. **Interact**:

    - In the client terminal, type messages to send to the server. Type `quit` to exit.

3. **TLS Payload Analysis**:

    - Use `Capture_payload_tls.py` to analyze a pcap file:

    ```bash
    python3 Capture_payload_tls.py --pcap path_to_file.pcap
    ```

    - The script will output a CSV file with estimated payload sizes.

## Advanced Components

- The `Mininet/Servers/` and `My_Simulator/` directories contain scripts for simulating more complex network environments, including TLS servers, web servers, and user authentication. These are useful for research or advanced experimentation.

## Requirements

- Python 3.x
- pyshark (for `Capture_payload_tls.py`)
- GNOME Terminal (for `start_proxy.sh`)

## Notes

- The code is intended for educational and experimental purposes.
- There is minimal error handling and security; do not use in production environments.

---
README.md written using GPT-4.1 in VSCode.
