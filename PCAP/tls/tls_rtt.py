#!/usr/bin/env python3
import csv
import tempfile
import os
import dpkt
import socket
import multiprocessing
from multiprocessing import Process, Queue
import argparse
import traceback
import struct   # FIXED: Missing import

PRINT_EVERY = 100000  # packets between verbose messages

def sort_csv_by_time(csv_file: str):
    """
    Sorts the CSV by the 'time' column (first column).
    This safely allows sorting in-place using a temporary file.
    """
    tmp_fd, tmp_path = tempfile.mkstemp()
    os.close(tmp_fd)

    # Read rows
    with open(csv_file, "r") as f:
        reader = csv.reader(f)
        header = next(reader)
        rows = list(reader)

    # Sort by first column (relative time)
    rows.sort(key=lambda x: float(x[0]))

    # Write sorted rows to temp file
    with open(tmp_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    # Replace original file
    os.replace(tmp_path, csv_file)


# ------------------------------------------------------
# True TLS packet detection
# ------------------------------------------------------
def parse_tls_packet(ts, first_ts, buf):
    try:
        eth = dpkt.ethernet.Ethernet(buf)
        ip = eth.data
        if not isinstance(ip, dpkt.ip.IP):
            return None

        tcp = ip.data
        if not isinstance(tcp, dpkt.tcp.TCP):
            return None

        payload = tcp.data
        if len(payload) < 5:
            return None

        # TLS Content Types
        content_type = payload[0]
        if content_type not in {20, 21, 22, 23}:  
            return None

        version_major = payload[1]
        version_minor = payload[2]

        # Valid TLS version 3.x
        if version_major != 3 or version_minor not in {0,1,2,3,4}:
            return None

        # TLS record length field
        tls_len = struct.unpack("!H", payload[3:5])[0]

        src = socket.inet_ntoa(ip.src)
        dst = socket.inet_ntoa(ip.dst)

        rel = ts - first_ts  # FIXED: correct relative time

        return f"{rel:.6f},{src},{tcp.sport},{dst},{tcp.dport},{tls_len}"

    except Exception:
        return None


# ------------------------------------------------------
# Worker: reads a defined range of packets
# ------------------------------------------------------
def worker_proc(start, end, filename, out_queue, prog_queue, first_ts, verbose):
    try:
        with open(filename, "rb") as f:
            pcap = dpkt.pcap.Reader(f)

            for idx, (ts, buf) in enumerate(pcap):
                if idx < start:
                    continue
                if idx >= end:
                    break

                prog_queue.put(1)

                row = parse_tls_packet(ts, first_ts, buf)
                if row:
                    out_queue.put(row)

    except Exception:
        traceback.print_exc()

    out_queue.put("##WORKER_DONE##")


# ------------------------------------------------------
# Collector: incremental CSV writer
# ------------------------------------------------------
def collector_proc(out_file, out_queue, worker_count):
    done = 0
    with open(out_file, "w") as f:
        f.write("time,src,src_port,dst,dst_port,length\n")

        while True:
            item = out_queue.get()

            if item == "##WORKER_DONE##":
                done += 1
                if done == worker_count:
                    break
                continue

            f.write(item + "\n")
            f.flush()


# ------------------------------------------------------
# Progress monitor
# ------------------------------------------------------
def progress_proc(prog_queue, verbose):
    total = 0

    while True:
        m = prog_queue.get()
        if m == "STOP":
            if verbose:
                print(f"[+] Final processed packets: {total:,}")
            break

        total += m

        if verbose and total % PRINT_EVERY == 0:
            print(f"[+] Processed {total:,} packets...")


# ------------------------------------------------------
# Fast packet count
# ------------------------------------------------------
def count_packets(filename):
    count = 0
    with open(filename, "rb") as f:
        for _ in dpkt.pcap.Reader(f):
            count += 1
    return count


# ------------------------------------------------------
# First timestamp
# ------------------------------------------------------
def get_first_timestamp(filename):
    with open(filename, "rb") as f:
        pcap = dpkt.pcap.Reader(f)
        for ts, _ in pcap:
            return ts
    return 0.0


# ------------------------------------------------------
# Main processing function
# ------------------------------------------------------
def process_pcap(input_file, output_file, workers, chunksize, verbose):
    print("[*] Counting packets...")
    total_packets = count_packets(input_file)
    print(f"[+] Total packets: {total_packets:,}")

    first_ts = get_first_timestamp(input_file)
    print("[+] First timestamp:", first_ts)

    out_queue = Queue()
    prog_queue = Queue()

    # Start collector
    collector = Process(target=collector_proc, args=(output_file, out_queue, workers))
    collector.start()

    # Start progress monitor
    progress = Process(target=progress_proc, args=(prog_queue, verbose))
    progress.start()

    # Launch workers
    procs = []
    for w in range(workers):
        start = w * chunksize
        end = min(start + chunksize, total_packets)

        if start >= total_packets:
            break

        p = Process(target=worker_proc,
                    args=(start, end, input_file, out_queue,
                          prog_queue, first_ts, verbose))
        procs.append(p)
        p.start()

    # Wait for workers
    for p in procs:
        p.join()

    prog_queue.put("STOP")
    progress.join()

    # Notify collector
    for _ in procs:
        out_queue.put("##WORKER_DONE##")

    collector.join()

    print("[+] Completed. Output saved to:", output_file)
    sort_csv_by_time(output_file)
    print("[+] CSV sorted by relative time.")



# ------------------------------------------------------
# CLI
# ------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Parallel TLS extractor using dpkt")

    parser.add_argument("-i", required=True, help="Input PCAP")
    parser.add_argument("-o", required=True, help="Output CSV")
    parser.add_argument("-w", "--workers", type=int, default=4, help="Num workers")
    parser.add_argument("-c", "--chunksize", type=int, default=500000)
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    process_pcap(args.i, args.o, args.workers, args.chunksize, args.verbose)


if __name__ == "__main__":
    main()
