#!/usr/bin/env python3
import os
import dpkt
import socket
import argparse
import multiprocessing as mp

# -------------------------------------------------------------------
# Utility
# -------------------------------------------------------------------
def inet_to_str(inet):
    try:
        return socket.inet_ntop(socket.AF_INET, inet)
    except ValueError:
        return socket.inet_ntop(socket.AF_INET6, inet)


# -------------------------------------------------------------------
# Worker process
# -------------------------------------------------------------------
def worker(packet_queue, result_queue):
    unique_ips = set()
    unique_sockets = set()
    unique_biflows = set()

    while True:
        item = packet_queue.get()
        if item == "STOP":
            break

        src_ip, src_port, dst_ip, dst_port = item

        # IPs
        unique_ips.add(src_ip)
        unique_ips.add(dst_ip)

        # sockets (one-direction, unique)
        if src_port:
            unique_sockets.add(f"{src_ip}:{src_port}")
        if dst_port:
            unique_sockets.add(f"{dst_ip}:{dst_port}")

        # bi-flow normalized
        if src_port and dst_port:
            a = f"{src_ip}:{src_port}"
            b = f"{dst_ip}:{dst_port}"
            flow = f"{a} <-> {b}" if a < b else f"{b} <-> {a}"
            unique_biflows.add(flow)

    # return partial result
    result_queue.put((unique_ips, unique_sockets, unique_biflows))


# -------------------------------------------------------------------
# Main pcap parser (single threaded streaming)
# -------------------------------------------------------------------
def parse_pcap_stream(pcap_path, packet_queue, verbose=False):
    with open(pcap_path, "rb") as f:
        try:
            pcap = dpkt.pcap.Reader(f)
        except Exception as e:
            print(f"[!] Failed to read {pcap_path}: {e}")
            return

        if verbose:
            print(f"[+] Streaming {pcap_path} ...")

        for ts, buf in pcap:
            try:
                eth = dpkt.ethernet.Ethernet(buf)
                if not isinstance(eth.data, dpkt.ip.IP):
                    continue

                ip = eth.data
                src_ip = inet_to_str(ip.src)
                dst_ip = inet_to_str(ip.dst)

                src_port = None
                dst_port = None

                if isinstance(ip.data, (dpkt.tcp.TCP, dpkt.udp.UDP)):
                    l4 = ip.data
                    src_port = l4.sport
                    dst_port = l4.dport

                # Send tuple to workers
                packet_queue.put((src_ip, src_port, dst_ip, dst_port))

            except Exception:
                continue


# -------------------------------------------------------------------
# Parallel PCAP processor
# -------------------------------------------------------------------
def process_pcap_parallel(pcap, out_dir, verbose):
    base = os.path.splitext(os.path.basename(pcap))[0]

    sockets_file = os.path.join(out_dir, f"{base}_unique_sockets.txt")
    biflows_file = os.path.join(out_dir, f"{base}_unique_biflows.txt")
    ip_file = os.path.join(out_dir, f"{base}_unique_ips.txt")

    # Queues
    packet_queue = mp.Queue(maxsize=500000)
    result_queue = mp.Queue()

    # Start workers
    cpu_count = mp.cpu_count()
    workers = []
    for _ in range(cpu_count):
        p = mp.Process(target=worker, args=(packet_queue, result_queue))
        p.start()
        workers.append(p)

    # Parse pcap and feed workers
    parse_pcap_stream(pcap, packet_queue, verbose)

    # Stop workers
    for _ in range(cpu_count):
        packet_queue.put("STOP")

    # Collect results
    all_ips = set()
    all_sockets = set()
    all_biflows = set()

    for _ in range(cpu_count):
        u_ips, u_sockets, u_biflows = result_queue.get()
        all_ips.update(u_ips)
        all_sockets.update(u_sockets)
        all_biflows.update(u_biflows)

    # Write output
    with open(sockets_file, "w") as f:
        for s in sorted(all_sockets):
            f.write(s + "\n")

    with open(biflows_file, "w") as f:
        for b in sorted(all_biflows):
            f.write(b + "\n")

    with open(ip_file, "w") as f:
        for ip in sorted(all_ips):
            f.write(ip + "\n")

    if verbose:
        print(f"[✓] Output written:")
        print(f"    {sockets_file}")
        print(f"    {biflows_file}")
        print(f"    {ip_file}")


# -------------------------------------------------------------------
# MAIN
# -------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Parallel PCAP unique extractor")
    parser.add_argument("-i", "--input", help="Pcap file or directory")
    parser.add_argument("-o", "--output", help="Output folder")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if not os.path.exists(args.output):
        os.makedirs(args.output)

    if os.path.isfile(args.input):
        process_pcap_parallel(args.input, args.output, args.verbose)

    else:
        for file in os.listdir(args.input):
            if file.endswith(".pcap") or file.endswith(".pcapng"):
                pcap_path = os.path.join(args.input, file)
                process_pcap_parallel(pcap_path, args.output, args.verbose)


if __name__ == "__main__":
    main()
