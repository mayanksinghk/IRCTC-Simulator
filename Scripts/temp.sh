#!/bin/bash

F1="../Data/ngetflow_int5_tcpdump.pcap"
echo $F1
F2="../Data/ngetflow_int5_tcpdump.pcap-unique_ips.txt"
echo $F2
F3="${F1::-5} $F2"
echo $F3