#!/usr/bin/env python3
import os
import time
import json
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from mininet.node import OVSController

class SimpleTopo(Topo):
    def build(self):
        client = self.addHost('client', ip='10.0.0.1/24')
        server = self.addHost('server', ip='10.0.0.2/24')
        s1 = self.addSwitch('s1')
        self.addLink(client, s1)
        self.addLink(server, s1)

def setup_environment():
    """Create required directories and delay profile."""
    os.makedirs('PCAP', exist_ok=True)
    os.makedirs('Logs', exist_ok=True)

    delay_file = 'delay.json'
    if not os.path.exists(delay_file):
        with open(delay_file, 'w') as f:
            json.dump({"delays_seconds": [0.010, 0.020, 0.050]}, f)
        info(f"*** Created synthetic delay profile at {delay_file}\n")

def run():
    setLogLevel('info')
    setup_environment()
    
    info('*** Creating the network\n')
    topo = SimpleTopo()
    net = Mininet(topo=topo, controller=OVSController)
    net.start()
    
    VENV_PY = "/home/mayank/Desktop/IRCTC/venv/bin/python3"
    
    # Get the current working directory where app.dist is located
    PROJECT_DIR = os.getcwd()

    server = net.get('server')
    client = net.get('client')

    # ==========================================
    # Apply TC Netem Delay using custom .dist
    # ==========================================
    info('*** Applying custom TC Netem distribution to server-eth0\n')
    # CHANGE '150ms' to your calculated average and '30ms' to your calculated jitter!
    # We pass TC_LIB_DIR so it finds app.dist in your current folder.
    server.cmd(f'TC_LIB_DIR={PROJECT_DIR} tc qdisc add dev server-eth0 root netem delay 45.18ms 53.41ms distribution app')

    info('*** Starting PCAP capture\n')
    client.cmd(f'tcpdump -i client-eth0 -s 0 -U --time-stamp-precision=nano -w PCAP/client.pcap &')
    server.cmd(f'tcpdump -i server-eth0 -s 0 -U --time-stamp-precision=nano -w PCAP/server.pcap &')

    time.sleep(1)  # ensure tcpdump is running

    info('*** Starting L4 Server (Port 80)\n')
    # NO_DELAY_MODE=1 ensures Python isn't adding delay, letting TC handle it entirely
    server.cmd(f'NO_DELAY_MODE=1 {VENV_PY} app_server.py > Logs/proxy.log 2>&1 &')
    time.sleep(2)
    
    info('*** Launching Traffic Generator from Client\n')
    client.cmdPrint(f'{VENV_PY} traffic_gen.py > Logs/Client.log 2>&1 &')
    print("*** EXPERIMENT COMPLETE ***")
    
    info('\n*** Dropping into interactive CLI for further testing\n')
    CLI(net)
    
    info('*** Cleaning up processes\n')

    # Stop tcpdump FIRST (important for proper file write)
    client.cmd('pkill tcpdump')
    server.cmd('pkill tcpdump')

    # Kill server app
    server.cmd('pkill -f app_server.py')
    
    # Remove the tc qdisc rule cleanly
    server.cmd('tc qdisc del dev server-eth0 root')

    net.stop()

if __name__ == '__main__':
    os.system('mn -c > /dev/null 2>&1')
    run()