#!/usr/bin/env python3
from mininet.topo import Topo
from mininet.net import Mininet
from mininet.cli import CLI
from mininet.node import Node
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
        # Switches in mininet cannot have descriptive name hence using this approach
        switches = {
            "isp": self.addSwitch('s1'),
            "dmz": self.addSwitch('s2'),
            "mz" : self.addSwitch('s3')
        }

        # ISP Cloud switch
        isp = self.addSwitch('sISP', dpid="0000000000000001")
        logging.debug("Added ISP switch")

        # Users
        user = self.addHost("user1", ip="10.0.0.1/24")
        self.addLink(user, isp)
        logging.debug("Added user host and linked to ISP switch")

        # CRIS DC Internet Router (entry point)
        router = self.addNode('r1', cls=LinuxRouter, ip="10.0.0.254/24")
        self.addLink(router, isp)
        logging.debug("Added router and linked to ISP switch")

        # Perimeter IPS
        ips = self.addHost('ips', ip="10.0.1.1/24")
        self.addLink(router, ips)
        logging.debug("Added IPS and linked to router")

        # Front End Firewall
        fw1 = self.addHost('fw1', ip="10.0.2.1/24")
        self.addLink(ips, fw1)
        logging.debug("Added Front End Firewall and linked to IPS")

        # DMZ Switch
        dmz = self.addSwitch('sDMZ', dpid="0000000000000002")
        self.addLink(fw1, dmz)
        logging.debug("Added DMZ switch and linked to Front End Firewall")

        # ADC (single host for now)
        adc = self.addHost("adc1", ip="10.0.3.1/24")
        self.addLink(adc, dmz)
        logging.debug("Added ADC and linked to DMZ switch")

        # WAF (single host for now)
        waf = self.addHost("waf1", ip="10.0.4.1/24")
        self.addLink(waf, dmz)
        logging.debug("Added WAF and linked to DMZ switch")

        # Web Server (fixed IP)
        web = self.addHost("web", ip="10.78.3.53/24")
        self.addLink(web, dmz)
        logging.debug("Added Web Server and linked to DMZ switch")

        # Back End Firewall
        fw2 = self.addHost('fw2', ip="10.0.5.1/24")
        self.addLink(dmz, fw2)
        logging.debug("Added Back End Firewall and linked to DMZ switch")

        # MZ Core Switch
        mz = self.addSwitch('sMZ', dpid="0000000000000003")
        self.addLink(fw2, mz)
        logging.debug("Added MZ Core switch and linked to Back End Firewall")

        # Server Load Balancer (single host for now)
        slb = self.addHost("slb1", ip="10.0.6.1/24")
        self.addLink(slb, mz)
        logging.debug("Added Server Load Balancer and linked to MZ Core switch")

        # Application Server (fixed IP)
        app = self.addHost("app", ip="10.78.3.51/24")
        self.addLink(app, mz)
        logging.debug("Added Application Server and linked to MZ Core switch")

def run():
    logging.debug("Starting CRIS DC Network Topology")
    topo = CRISDCNetwork()
    net = Mininet(topo=topo, controller=None)
    net.start()

    # Enable routing on router and firewalls
    logging.debug("Enabling IP forwarding on routers and firewalls")
    net.get('r1').cmd("sysctl -w net.ipv4.ip_forward=1")
    net.get('fw1').cmd("sysctl -w net.ipv4.ip_forward=1")
    net.get('fw2').cmd("sysctl -w net.ipv4.ip_forward=1")

    print("\nNetwork ready. Use CLI to test.\n")
    CLI(net)
    logging.debug("Stopping network\n")
    net.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    run()
