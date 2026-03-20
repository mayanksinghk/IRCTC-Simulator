#!/usr/bin/env python3
import os
import time
import logging
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.node import Node, OVSSwitch
from mininet.term import makeTerm

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("IRCTC-Sim")

class LinuxRouter(Node):
    """A Node with IP forwarding enabled (for router/firewall use)."""
    def config(self, **params):
        super(LinuxRouter, self).config(**params)
        self.cmd("sysctl -w net.ipv4.ip_forward=1")
    def terminate(self):
        self.cmd("sysctl -w net.ipv4.ip_forward=0")
        super(LinuxRouter, self).terminate()

class CRISDCNetwork(Topo):
    def build(self):
        # 1. External Access (Fixed Switch Name)
        user = self.addHost("user1", ip="10.0.0.1/24")
        s1 = self.addSwitch('s1', cls=OVSSwitch, failMode='standalone')
        
        # 2. Border Control
        r1 = self.addNode('r1', cls=LinuxRouter, ip='10.0.0.254/24')
        ips = self.addNode('ips', cls=LinuxRouter, ip="10.0.1.253/24")
        fw1 = self.addHost('fw1', ip="10.0.2.253/24")
        
        # 3. DMZ Layer (Fixed Switch Name)
        s2 = self.addSwitch('s2', cls=OVSSwitch, failMode='standalone')
        adc = self.addHost("adc1", ip="10.0.3.1/24")
        waf = self.addHost("waf1", ip="10.0.3.2/24")
        web = self.addHost("web", ip="10.0.3.3/24")
        fw2 = self.addHost('fw2', ip="10.0.3.253/24")
        
        # 4. Management Zone (Fixed Switch Name)
        s3 = self.addSwitch('s3', cls=OVSSwitch, failMode='standalone')
        slb = self.addHost("slb1", ip="10.0.4.1/24")
        app = self.addHost("app", ip="10.0.4.2/24")

        # Links
        self.addLink(user, s1)
        self.addLink(r1, s1)
        self.addLink(r1, ips)
        self.addLink(ips, fw1)
        self.addLink(fw1, s2)
        self.addLink(adc, s2)
        self.addLink(waf, s2)
        self.addLink(web, s2)
        self.addLink(fw2, s2)
        self.addLink(fw2, s3)
        self.addLink(slb, s3)
        self.addLink(app, s3)

def run():
    logger.info("Starting CRIS DC Network Emulation")
    topo = CRISDCNetwork()
    net = Mininet(topo=topo, controller=None)
    net.start()

    # ==========================
    # 1. Interface & IP Forwarding Configuration
    # ==========================
    logger.info("Configuring interfaces and routing...")
    net.get('r1').setIP("10.0.1.254/24", intf='r1-eth1')
    net.get('ips').setIP("10.0.2.254/24", intf='ips-eth1')
    net.get('fw1').setIP("10.0.3.254/24", intf='fw1-eth1')
    net.get('fw2').setIP("10.0.4.254/24", intf='fw2-eth1')

    # Enable Forwarding on hosts acting as firewalls
    for n in ['fw1', 'fw2']:
        net.get(n).cmd("sysctl -w net.ipv4.ip_forward=1")

    # ==========================
    # 2. Explicit Routing Matrix
    # ==========================
    # --- R1 Routes ---
    r1 = net.get('r1')
    r1.cmd("ip route add 10.0.2.0/24 via 10.0.1.253")
    r1.cmd("ip route add 10.0.3.0/24 via 10.0.1.253")
    r1.cmd("ip route add 10.0.4.0/24 via 10.0.1.253")

    # --- IPS Routes ---
    ips = net.get('ips')
    ips.cmd("ip route add 10.0.0.0/24 via 10.0.1.254") 
    ips.cmd("ip route add 10.0.3.0/24 via 10.0.2.253") 
    ips.cmd("ip route add 10.0.4.0/24 via 10.0.2.253") 

    # --- FW1 Routes ---
    fw1 = net.get('fw1')
    fw1.cmd("ip route add 10.0.0.0/24 via 10.0.2.254") 
    fw1.cmd("ip route add 10.0.1.0/24 via 10.0.2.254") 
    fw1.cmd("ip route add 10.0.4.0/24 via 10.0.3.253") 

    # --- FW2 Routes ---
    fw2 = net.get('fw2')
    fw2.cmd("ip route add 10.0.0.0/24 via 10.0.3.254") 
    fw2.cmd("ip route add 10.0.1.0/24 via 10.0.3.254") 
    fw2.cmd("ip route add 10.0.2.0/24 via 10.0.3.254") 

    # --- Endpoint Gateways ---
    for host in net.hosts:
        host.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        host.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
        if host.name not in ['r1', 'ips', 'fw1', 'fw2']:
            subnet = host.IP().split('.')[2]
            gw = f"10.0.{subnet}.254"
            host.cmd("ip route flush root 0/0")
            host.cmd(f"ip route add default via {gw}")

    # ==========================
    # 3. Packet Captures (Checksums Disabled for Analysis)
    # ==========================
    logger.info("Starting background packet captures...")
    nodes_to_capture = ['adc1', 'waf1', 'web', 'fw2', 'app']
    
    for name in nodes_to_capture:
        node = net.get(name)
        for intf in node.intfList():
            node.cmd(f'ethtool -K {intf.name} tx off rx off')
        # Capture both HTTP and HTTPS
        # node.cmd(f'tcpdump -i any -w {name}_emulated.pcap "tcp port 80 or tcp port 443" -n -U &')
        # Force tcpdump to write to /tmp/ and capture any error messages!
        node.cmd(f'tcpdump -i any -w /tmp/{name}_emulated.pcap "tcp port 80 or tcp port 443" -n -U > {name}_tcpdump.log 2>&1 &')

    # ==========================
    # 4. Start Empirical Delay Proxies (The Chain)
    # ==========================
    logger.info("Starting the Delay Proxy Chain...")
    
    def start_p(node, profile, b_ip, b_port=80, listen_port=80, cert=None, key=None):
        # Use the absolute path to your specific virtual environment
        venv_python = "/home/mayank/Desktop/IRCTC/venv/bin/python"
        cmd = f"{venv_python} delay_proxy.py -b {b_ip} --bport {b_port} --port {listen_port}"
        # Point to the Mininet_Profiles directory from your earlier steps
        if profile and os.path.exists(f"./Mininet_Profiles/{profile}"): 
            cmd += f" -c ./Mininet_Profiles/{profile}"
        if cert and key and os.path.exists(cert): 
            cmd += f" --cert {cert} --key {key}"
        node.cmd(f"{cmd} > {node.name}_proxy.log 2>&1 &")

    # 1. App Server (Local 8080 backend)
    net.get('app').cmd('/home/mayank/Desktop/IRCTC/venv/bin/python -m http.server 8080 &')
    start_p(net.get('app'), "app_isolated.csv", "127.0.0.1", 8080)
    
    # 2. SLB -> App
    start_p(net.get('slb1'), None, "10.0.4.2")
    
    # 3. FW2 -> SLB
    start_p(net.get('fw2'), "fw_isolated.csv", "10.0.4.1")
    
    # 4. Web Server -> FW2
    start_p(net.get('web'), "web_isolated.csv", "10.0.3.253")
    
    # 5. WAF -> Web Server
    start_p(net.get('waf1'), "waf_isolated.csv", "10.0.3.3")
    
    # 6. ADC (TLS Edge) -> WAF. Listens on 443, decrypts, and forwards to 80.
    start_p(net.get('adc1'), "adc_isolated.csv", "10.0.3.2", b_port=80, listen_port=443, cert="adc_cert.pem", key="adc_key.pem")

    time.sleep(5) # Wait for proxies to bind

    # ==========================
    # 5. Launch Traffic
    # ==========================
    print("\n" + "="*60)
    print("EMULATION READY: Automatically starting 1000 concurrent TLS requests.")
    print("Monitor progress with: tail -f user1_load_results.txt")
    print("="*60 + "\n")
    
    # Run 1000 requests, 50 at a time, using parallel curl processes
    load_cmd = "bash -c 'seq 1 1000 | xargs -n 1 -P 50 -I {} curl -s -k -o /dev/null -w \"%{http_code}\\n\" https://10.0.3.1/' > user1_load_results.txt &"
    net.get('user1').cmd(load_cmd)

    CLI(net)

    # ==========================
    # 6. Cleanup Loop
    # ==========================
    logger.info("Cleaning up background processes...")
    for name in nodes_to_capture:
        net.get(name).cmd('pkill tcpdump')
        
    for name in ['adc1', 'waf1', 'web', 'fw2', 'slb1', 'app']:
        net.get(name).cmd('pkill -f delay_proxy.py')
        net.get(name).cmd('pkill -f http.server') 
        
    logger.info("Cleanup complete. PCAPs are ready for analysis.")
    net.stop()

if __name__ == "__main__":
    run()