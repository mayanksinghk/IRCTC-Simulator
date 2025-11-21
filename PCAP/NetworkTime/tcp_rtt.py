#!/usr/bin/env python3
import dpkt
import socket
import argparse
from collections import defaultdict, deque
from tqdm import tqdm

def inet_to_str(inet):
    try:
        return socket.inet_ntop(socket.AF_INET, inet)
    except ValueError:
        return socket.inet_ntop(socket.AF_INET6, inet)

def parse_packet(buf):
    try:
        eth = dpkt.ethernet.Ethernet(buf)
        ip = eth.data
        if not isinstance(ip, (dpkt.ip.IP, dpkt.ip6.IP6)):
            return None
        if ip.p != dpkt.ip.IP_PROTO_TCP:
            return None
        tcp = ip.data
        if not isinstance(tcp, dpkt.tcp.TCP):
            return None
        src_ip = inet_to_str(ip.src)
        dst_ip = inet_to_str(ip.dst)
        return tcp, src_ip, dst_ip
    except Exception:
        return None

def main():
    parser = argparse.ArgumentParser(description="Simple TCP RTT extractor")
    parser.add_argument("-p", "--pcap", required=True)
    parser.add_argument("-o", "--output", default="rtt_times.txt")
    parser.add_argument("-i", "--ip-list", help="Optional IP filter")
    args = parser.parse_args()

    filter_ips = set()
    if args.ip_list:
        with open(args.ip_list) as f:
            filter_ips = set(line.strip() for line in f if line.strip())

    seq_times = defaultdict(deque)

    with open(args.pcap, "rb") as f, open(args.output, "w") as out:
        try:
            reader = dpkt.pcap.Reader(f)
        except (ValueError, dpkt.dpkt.NeedData):
            f.seek(0)
            reader = dpkt.pcapng.Reader(f)

        for ts, buf in tqdm(reader, desc="Processing packets"):
            pkt = parse_packet(buf)
            if pkt is None:
                continue
            tcp, src_ip, dst_ip = pkt

            if filter_ips and src_ip not in filter_ips and dst_ip not in filter_ips:
                continue

            key = (src_ip, tcp.sport, dst_ip, tcp.dport)
            rev_key = (dst_ip, tcp.dport, src_ip, tcp.sport)

            payload_len = len(tcp.data)
            seq_start = tcp.seq
            seq_end = tcp.seq + payload_len

            if payload_len > 0:
                # store seq and timestamp
                seq_times[key].append((seq_start, seq_end, ts))
            else:
                # ACK: match reverse direction
                queue = seq_times[rev_key]
                remove_indices = []
                for idx, (s_start, s_end, ts_data) in enumerate(queue):
                    if tcp.ack >= s_end:
                        rtt = ts - ts_data
                        if rtt > 0:
                            out.write(f"{rtt}\n")
                        remove_indices.append(idx)
                # remove matched entries
                for idx in reversed(remove_indices):
                    del queue[idx]

    print(f"[+] Done. RTTs saved in {args.output}")

if __name__ == "__main__":
    main()
