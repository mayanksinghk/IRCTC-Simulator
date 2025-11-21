#!/usr/bin/env python3
import os
import argparse
from scapy.all import PcapReader, TCP, IP
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from collections import defaultdict

def process_chunk(chunk, verbose=False):
    """Process a chunk of packets, calculate RTTs per TCP 4-tuple"""
    rtt_list = []
    # Track last sent sequence numbers for each connection
    conn_state = defaultdict(dict)  # {(src,dst,sport,dport): {seq: time}}
    
    for pkt in chunk:
        if IP in pkt and TCP in pkt:
            ip_layer = pkt[IP]
            tcp_layer = pkt[TCP]
            src = ip_layer.src
            dst = ip_layer.dst
            sport = tcp_layer.sport
            dport = tcp_layer.dport
            seq = tcp_layer.seq
            ack = tcp_layer.ack
            time = float(pkt.time)
            flags = tcp_layer.flags

            # Create connection key
            conn = (src, dst, sport, dport)
            rev_conn = (dst, src, dport, sport)

            # If packet is ACK, check if we have matching sequence
            if flags & 0x10:  # ACK flag
                for s_seq, s_time in list(conn_state[rev_conn].items()):
                    if s_seq == ack - 1:  # approximate match
                        rtt = time - s_time
                        if rtt >= 0:
                            rtt_list.append(rtt)
                        del conn_state[rev_conn][s_seq]
            else:
                # Track sequence number for future ACK
                conn_state[conn][seq] = time

    if verbose:
        print(f"[+] Chunk processed, RTTs found: {len(rtt_list)}")
    return rtt_list

def read_chunks(pcap_file, chunk_size=100000):
    """Generator to read packets in chunks"""
    chunk = []
    total_packets = 0
    with PcapReader(pcap_file) as pcap:
        for pkt in pcap:
            chunk.append(pkt)
            total_packets += 1
            if len(chunk) >= chunk_size:
                yield chunk, total_packets
                chunk = []
        if chunk:
            yield chunk, total_packets

def main():
    parser = argparse.ArgumentParser(description="Calculate TCP RTTs from PCAP (parallel, streaming)")
    parser.add_argument("-i", "--input", required=True, help="Input PCAP file")
    parser.add_argument("-o", "--output", required=True, help="Output RTT txt file")
    parser.add_argument("-c", "--chunk-size", type=int, default=100000, help="Packets per chunk")
    parser.add_argument("-w", "--workers", type=int, default=None, help="Number of parallel workers (default: CPU-1)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose progress")
    args = parser.parse_args()

    output_file = args.output
    os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)

    import multiprocessing
    workers = args.workers or max(1, multiprocessing.cpu_count() - 1)

    all_rtts = []

    print(f"[*] Using {workers} workers")
    print(f"[*] Reading packets from {args.input} in chunks of {args.chunk_size}")

    with ThreadPoolExecutor(max_workers=workers) as exe, open(output_file, "w") as f_out:
        futures = {}
        for chunk, total_packets in read_chunks(args.input, args.chunk_size):
            future = exe.submit(process_chunk, chunk, args.verbose)
            futures[future] = total_packets

        for future in tqdm(as_completed(futures), total=len(futures), desc="Processing chunks"):
            rtts = future.result()
            for rtt in rtts:
                f_out.write(f"{rtt:.6f}\n")

    print(f"[+] RTT calculation complete, results saved to {output_file}")
    print(f"[+] Total RTT samples: {sum(1 for _ in open(output_file))}")

if __name__ == "__main__":
    main()
