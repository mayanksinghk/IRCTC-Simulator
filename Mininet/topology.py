#!/usr/bin/env python3
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.node import Node
from mininet.node import OVSSwitch
import logging


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
        # Users
        user = self.addHost("user1", ip="10.0.0.1/24")
        logging.debug("Added user host and linked to ISP switch")

        # ISP Cloud switch
        isp = self.addSwitch('sISP', cls=OVSSwitch, failMode='standalone', dpid="0000000000000001")
        self.addLink(user, isp)
        logging.debug("Added ISP switch")

        # CRIS DC Internet Router (entry point)
        router = self.addNode('r1', cls=LinuxRouter, ip='10.0.0.254/24')
        self.addLink(router, isp)
        logging.debug("Added router and linked to ISP switch")

        # Perimeter IPS
        ips = self.addNode('ips', cls=LinuxRouter, ip="10.0.1.253/24")
        self.addLink(router, ips)
        logging.debug("Added IPS and linked to router")

        # Front End Firewall
        fw1 = self.addHost('fw1', ip="10.0.2.253/24")
        self.addLink(ips, fw1)
        logging.debug("Added Front End Firewall and linked to IPS")

        # DMZ Switch
        dmz = self.addSwitch('sDMZ', cls=OVSSwitch, failMode='standalone', dpid="0000000000000002")
        self.addLink(fw1, dmz)
        logging.debug("Added DMZ switch and linked to Front End Firewall")

        # ADC (single host for now)
        adc = self.addHost("adc1", ip="10.0.3.1/24")
        self.addLink(adc, dmz)
        logging.debug("Added ADC and linked to DMZ switch")

        # WAF (single host for now)
        waf = self.addHost("waf1", ip="10.0.3.2/24")
        self.addLink(waf, dmz)
        logging.debug("Added WAF and linked to DMZ switch")

        # Web Server (fixed IP)
        web = self.addHost("web", ip="10.0.3.3/24")
        self.addLink(web, dmz)
        logging.debug("Added Web Server and linked to DMZ switch")

        # Back End Firewall
        fw2 = self.addHost('fw2', ip="10.0.3.253/24")
        self.addLink(dmz, fw2)
        logging.debug("Added Back End Firewall and linked to DMZ switch")

        # MZ Core Switch
        mz = self.addSwitch('sMZ', cls=OVSSwitch, failMode='standalone', dpid="0000000000000003")
        self.addLink(fw2, mz)
        logging.debug("Added MZ Core switch and linked to Back End Firewall")

        # Server Load Balancer (single host for now)
        slb = self.addHost("slb1", ip="10.0.4.1/24")
        self.addLink(slb, mz)
        logging.debug("Added Server Load Balancer and linked to MZ Core switch")

        # Application Server (fixed IP)
        app = self.addHost("app", ip="10.0.4.2/24")
        self.addLink(app, mz)
        logging.debug("Added Application Server and linked to MZ Core switch")

def run():
    logging.debug("Starting CRIS DC Network Topology")
    topo = CRISDCNetwork()
    net = Mininet(topo=topo, controller=None)
    net.start()

    # Enable routing on router and firewalls
    logging.debug("Enabling IP forwarding on routers and firewalls")

    # Printing IP addresses for verification, 
    logging.debug("Network setup complete. Hosts and their IPs:")
    for host in net.hosts:
        # Disable ipv6 interface as we are working with ipv4 only and it creates unecessary clashes 
        host.cmd("sysctl -w net.ipv6.conf.all.disable_ipv6=1")
        host.cmd("sysctl -w net.ipv6.conf.default.disable_ipv6=1")
        logging.debug(f"{host.name}: {host.IP()}")

    net.get('r1').setIP("10.0.1.254/24", intf='r1-eth1')    # Router to IPS
    net.get('ips').setIP("10.0.2.254", intf='ips-eth1')     # IPS to Frontend FW
    net.get('fw1').setIP("10.0.3.254/24", intf='fw1-eth1')  # Frontend FW to DMZ
    net.get('fw2').setIP("10.0.4.254/24", intf='fw2-eth1')  # Backend FW to MZ Core

    # # IPv4 packet forwarding at your routers/firewalls
    # for node in ['r1', 'fw1', 'fw2', 'ips']:   
    #     net.get(node).cmd("sysctl -w net.ipv4.ip_forward=1")
    #     net.get(node).cmd(f"zebra -d -f /home/mayank/Desktop/IRCTC/IRCTC-Simulator/Mininet/zebra/{node}_zebra.conf")
    #     net.get(node).cmd(f"rpid -d -f /home/mayank/Desktop/IRCTC/IRCTC-Simulator/Mininet/rpid/{node}_rpid.conf")

    for host in net.hosts:
        # Pick the first interface's subnet as reference
        intf = host.intfNames()[0]          # e.g., user1-eth0
        ip = host.IP(intf=intf)             # e.g., 10.0.0.1
        if host.name not in ['r1', 'ips', 'fw1', 'fw2']:
            print(host)
            # Assuming the router is the last IP in the subnet
            subnet = ip.split('.')[:3]          # ['10','0','0']
            gw = '.'.join(subnet + ['254'])    # e.g., 10.0.0.254
            host.cmd(f'ip route add default via {gw} dev {intf}')

     # ==========================
    # Static Routes for r1
    # ==========================
    r1 = net.get('r1')
    r1.cmd("ip route add 10.0.2.0/24 via 10.0.1.253 dev r1-eth1")  # FW1 via IPS
    r1.cmd("ip route add 10.0.3.0/24 via 10.0.1.253 dev r1-eth1")  # DMZ
    r1.cmd("ip route add 10.0.4.0/24 via 10.0.1.253 dev r1-eth1")  # MZ Switch
    r1.cmd("ip route add 10.0.5.0/24 via 10.0.1.253 dev r1-eth1")  # SLB / App

    # ==========================
    # Static Routes for IPS
    # ==========================
    ips = net.get('ips')
    ips.cmd("ip route add 10.0.0.0/24 via 10.0.1.254 dev ips-eth0")  # to User
    ips.cmd("ip route add 10.0.3.0/24 via 10.0.2.253 dev ips-eth1")  # DMZ
    ips.cmd("ip route add 10.0.4.0/24 via 10.0.2.253 dev ips-eth1")  # MZ
    ips.cmd("ip route add 10.0.5.0/24 via 10.0.2.253 dev ips-eth1")  # SLB / App

    # ==========================
    # Static Routes for FW1
    # ==========================
    fw1 = net.get('fw1')
    fw1.cmd("ip route add 10.0.0.0/24 via 10.0.2.254 dev fw1-eth0")  # User
    fw1.cmd("ip route add 10.0.1.0/24 via 10.0.2.254 dev fw1-eth0")  # IPS
    fw1.cmd("ip route add 10.0.4.0/24 via 10.0.3.253 dev fw1-eth1")  # MZ Core
    fw1.cmd("ip route add 10.0.5.0/24 via 10.0.3.253 dev fw1-eth1")  # SLB / App

    # ==========================
    # Static Routes for FW2
    # ==========================
    fw2 = net.get('fw2')
    fw2.cmd("ip route add 10.0.0.0/24 via 10.0.3.254 dev fw2-eth0")  # User via DMZ
    fw2.cmd("ip route add 10.0.1.0/24 via 10.0.3.254 dev fw2-eth0")  # IPS via DMZ
    fw2.cmd("ip route add 10.0.2.0/24 via 10.0.3.254 dev fw2-eth0")  # FW1 via DMZ
    fw2.cmd("ip route add 10.0.3.0/24 dev fw2-eth0")                # DMZ subnet
    fw2.cmd("ip route add 10.0.4.0/24 via 10.0.4.1 dev fw2-eth1")  # MZ Core

    print("\nNetwork ready. Use CLI to test.\n")
    CLI(net)
    logging.debug("Stopping network\n")
    net.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    run()
