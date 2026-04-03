#!/usr/bin/env python3
import os
import time
import logging
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.node import Node, OVSSwitch

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
        # 1. External Access
        user = self.addHost("user1", ip="10.0.0.1/24")
        s1 = self.addSwitch('s1', cls=OVSSwitch, failMode='standalone')
        
        # 2. Border Control
        r1 = self.addNode('r1', cls=LinuxRouter, ip='10.0.0.254/24')
        ips = self.addNode('ips', cls=LinuxRouter, ip="10.0.1.253/24")
        fw1 = self.addHost('fw1', ip="10.0.2.253/24")
        
        # 3. DMZ Layer
        s2 = self.addSwitch('s2', cls=OVSSwitch, failMode='standalone')
        adc = self.addHost("adc1", ip="10.0.3.1/24")
        waf = self.addHost("waf1", ip="10.0.3.2/24")
        web = self.addHost("web", ip="10.0.3.3/24")
        fw2 = self.addHost('fw2', ip="10.0.3.253/24")
        
        # 4. Management Zone
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
    logger.info("Preparing environment...")
    
    # Ensure directories exist on the host machine
    directories = ['Logs', 'PCAP', 'mininet_delays']
    for d in directories:
        if not os.path.exists(d):
            os.makedirs(d)
            logger.info(f"Created directory: {d}")

    logger.info("Starting CRIS DC Network Emulation")
    topo = CRISDCNetwork()
    net = Mininet(topo=topo, controller=None)
    net.start()

    # ==========================
    # 1. System & Interface Tuning
    # ==========================
    logger.info("Tuning Kernel and Limits for high concurrency...")
    for node in net.values():
        node.cmd("ulimit -n 8192") # Boost file descriptors
        node.cmd("sysctl -w net.core.somaxconn=2048") # Increase listen backlog
        node.cmd("sysctl -w net.ipv4.tcp_max_syn_backlog=2048")
        node.cmd("sysctl -w net.ipv4.ip_local_port_range='1024 65535'")

    # Configuration of IP Addresses across hops
    net.get('r1').setIP("10.0.1.254/24", intf='r1-eth1')
    net.get('ips').setIP("10.0.2.254/24", intf='ips-eth1')
    net.get('fw1').setIP("10.0.3.254/24", intf='fw1-eth1')
    net.get('fw2').setIP("10.0.4.254/24", intf='fw2-eth1')

    # Enable Forwarding
    for n in ['fw1', 'fw2']:
        net.get(n).cmd("sysctl -w net.ipv4.ip_forward=1")

    # ==========================
    # 2. Routing Matrix
    # ==========================
    r1 = net.get('r1')
    r1.cmd("ip route add 10.0.2.0/24 via 10.0.1.253")
    r1.cmd("ip route add 10.0.3.0/24 via 10.0.1.253")
    r1.cmd("ip route add 10.0.4.0/24 via 10.0.1.253")

    ips = net.get('ips')
    ips.cmd("ip route add 10.0.0.0/24 via 10.0.1.254") 
    ips.cmd("ip route add 10.0.3.0/24 via 10.0.2.253") 
    ips.cmd("ip route add 10.0.4.0/24 via 10.0.2.253") 

    fw1 = net.get('fw1')
    fw1.cmd("ip route add 10.0.0.0/24 via 10.0.2.254") 
    fw1.cmd("ip route add 10.0.1.0/24 via 10.0.2.254") 
    fw1.cmd("ip route add 10.0.4.0/24 via 10.0.3.253") 

    fw2 = net.get('fw2')
    fw2.cmd("ip route add 10.0.0.0/24 via 10.0.3.254") 
    fw2.cmd("ip route add 10.0.1.0/24 via 10.0.3.254") 
    fw2.cmd("ip route add 10.0.2.0/24 via 10.0.3.254") 

    for host in net.hosts:
        host.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        if host.name not in ['r1', 'ips', 'fw1', 'fw2']:
            subnet = host.IP().split('.')[2]
            gw = f"10.0.{subnet}.254"
            host.cmd(f"ip route add default via {gw}")
    
    # --- PCAP CAPTURE START ---
    # We capture at IPS and ADC1 to verify the GMM delay injection
    logger.info("Starting background packet captures...")
    nodes_to_capture = ['user1', 'ips', 'adc1', 'app', 'waf1', 'web', 'fw2']
    
    for name in nodes_to_capture:
        node = net.get(name)
        # Disable hardware offloading to ensure pcap captures actual packet sizes
        for intf in node.intfList():
            node.cmd(f'ethtool -K {intf.name} tx off rx off')
        
        # Capture TCP traffic on ports 80 and 443
        # -U ensures the buffer is flushed immediately so you don't lose data on crash
        pcap_file = f"{os.getcwd()}/PCAP/{name}.pcap"
        log_file = f"{os.getcwd()}/Logs/{name}_tcpdump.log"
        node.cmd(f'tcpdump -i any "tcp port 80 or tcp port 443" -n -U -w {pcap_file} > {log_file} 2>&1 &')
    # --- PCAP CAPTURE END ---


    # ==========================
    # 3. Startup Specialized Scripts
    # ==========================
    logger.info("Starting specialized node proxies...")
    venv_python = "/home/mayank/Desktop/IRCTC/venv/bin/python3"
    script_dir = "/home/mayank/Desktop/IRCTC/IRCTC-Simulator/docs/Mininet/Servers"

    # Terminal Logic
    net.get('app').cmd(f'{venv_python} {script_dir}/fast_app.py > Logs/app_backend.log 2>&1 &')
    net.get('app').cmd(f'{venv_python} {script_dir}/app_server_node.py > Logs/app_proxy.log 2>&1 &')
    
    # Management Zone
    net.get('slb1').cmd(f'{venv_python} {script_dir}/slb_node.py > Logs/slb.log 2>&1 &')
    net.get('fw2').cmd(f'{venv_python} {script_dir}/fw2_node.py > Logs/fw2.log 2>&1 &')
    
    # DMZ Zone
    net.get('web').cmd(f'{venv_python} {script_dir}/web_node.py > Logs/web.log 2>&1 &')
    net.get('waf1').cmd(f'{venv_python} {script_dir}/waf_node.py > Logs/waf.log 2>&1 &')
    net.get('adc1').cmd(f'{venv_python} {script_dir}/adc_node.py > Logs/adc.log 2>&1 &')

    # IPS Transparent Interception
    ips_n = net.get('ips')
    ips_n.cmd('iptables -t nat -A PREROUTING -p tcp --dport 443 -j REDIRECT --to-ports 443')
    ips_n.cmd(f'{venv_python} {script_dir}/ips_node.py > Logs/ips.log 2>&1 &')

    time.sleep(5) # Allow bindings

    # ==========================
    # 4. Traffic & Cleanup
    # ==========================
    logger.info("Launching Traffic Generator...")
    net.get('user1').cmd(f'bash -c "{venv_python} traffic_gen.py > user1_load_results.txt 2>&1" &')

    CLI(net)

    logger.info("Cleaning up...")
    for node in net.hosts:
        node.cmd('pkill -f "_node.py"')
        node.cmd('pkill -f "fast_app.py"')
    net.stop()

if __name__ == "__main__":
    run()