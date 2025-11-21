#!/usr/bin/env python3
"""
http_rtt_matcher_fixed.py
Fully working HTTP Request→Response matcher with RELATIVE TIME.
Fixes:
 - Corrected flow direction logic
 - Correct HTTP request/response detection
 - seq_end <= ack matching corrected
 - First packet timestamp shared globally
 - Produces non-empty CSV
"""

from __future__ import annotations
import argparse
import dpkt
import socket
import multiprocessing as mp
from multiprocessing import Process, Queue, Value, Lock
import csv
import os
from collections import defaultdict, deque
import time

PRINT_INTERVAL = 100_000

# ----------------------------
# GLOBAL VALUES (shared)
# ----------------------------
progress = Value('Q', 0)
progress_lock = Lock()

first_ts = Value('d', 0.0)
first_ts_set = Value('b', False)
first_ts_lock = Lock()

HTTP_REQ_METHODS = (
    b"GET ", b"POST ", b"PUT ", b"DELETE ", b"HEAD ",
    b"OPTIONS ", b"PATCH "
)

HTTP_RESP_PREFIX = b"HTTP/"


def update_progress():
    with progress_lock:
        progress.value += 1
        if progress.value % PRINT_INTERVAL == 0:
            print(f"[+] Processed {progress.value:,} packets...")


def inet(addr):
    try:
        return socket.inet_ntop(socket.AF_INET, addr)
    except:
        return ".".join(str(b) for b in addr)


def get_relative_ts(ts):
    """Returns ts relative to first packet of the pcap."""
    with first_ts_lock:
        if not first_ts_set.value:
            first_ts.value = ts
            first_ts_set.value = True
        return ts - first_ts.value


# ----------------------------
# Worker
# ----------------------------
def worker_main(task_q, result_q, verbose):
    req_store = defaultdict(deque)

    while True:
        item = task_q.get()
        if item == "STOP":
            break

        ts, buf = item
        rel_ts = get_relative_ts(ts)

        try:
            eth = dpkt.ethernet.Ethernet(buf)
            ip = eth.data
            if not isinstance(ip, dpkt.ip.IP):
                update_progress()
                continue

            tcp = ip.data
            if not isinstance(tcp, dpkt.tcp.TCP):
                update_progress()
                continue

            data = tcp.data
            if not data:
                update_progress()
                continue

            src = inet(ip.src)
            dst = inet(ip.dst)
            sport = tcp.sport
            dport = tcp.dport

            # ======================================
            # 1. Detect HTTP REQUEST (client → server)
            # ======================================
            is_request = any(data.startswith(m) for m in HTTP_REQ_METHODS)

            if is_request:
                flow_key = (src, sport, dst, dport)

                seq_start = tcp.seq
                seq_end = seq_start + len(data)

                # Extract method + URI from first line
                method = ""
                uri = ""
                try:
                    line = data.split(b"\r\n", 1)[0].decode(errors="replace")
                    parts = line.split()
                    if len(parts) >= 1:
                        method = parts[0]
                    if len(parts) >= 2:
                        uri = parts[1]
                except:
                    pass

                req_store[flow_key].append({
                    "req_time": rel_ts,
                    "seq_end": seq_end,
                    "size": len(data),
                    "uri": uri,
                    "method": method,
                })

                update_progress()
                continue

            # ======================================
            # 2. Detect HTTP RESPONSE (server → client)
            # ======================================
            if data.startswith(HTTP_RESP_PREFIX):
                # Reverse flow → match to client's request
                flow_key = (dst, dport, src, sport)

                if flow_key not in req_store:
                    update_progress()
                    continue

                ack = tcp.ack
                q = req_store[flow_key]

                matched = None
                if q:
                    # find earliest where seq_end <= ack
                    if q[0]["seq_end"] <= ack:
                        matched = q.popleft()

                if matched:
                    result_q.put({
                        "client_ip": flow_key[0],
                        "client_port": flow_key[1],
                        "server_ip": flow_key[2],
                        "server_port": flow_key[3],

                        "method": matched["method"],
                        "uri": matched["uri"],

                        "request_time_rel": matched["req_time"],
                        "response_time_rel": rel_ts,
                        "rtt": rel_ts - matched["req_time"],

                        "request_size": matched["size"],
                        "response_size": len(data)
                    })


                update_progress()
                continue

            update_progress()

        except Exception:
            update_progress()
            continue

    result_q.put("WORKER_DONE")


# ----------------------------
# Aggregator (CSV writer)
# ----------------------------
def aggregator_main(result_q, out_csv, n_workers):
    done = 0

    with open(out_csv, "w", newline='', encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow([
            "method",
            "client_ip", "client_port", "server_ip", "server_port",
            "uri",
            "request_time_rel", "response_time_rel", "rtt",
            "request_size", "response_size"
        ])


        while done < n_workers:
            item = result_q.get()
            if item == "WORKER_DONE":
                done += 1
                continue

            w.writerow([
                item["method"],
                item["client_ip"], item["client_port"],
                item["server_ip"], item["server_port"],
                item["uri"],
                f"{item['request_time_rel']:.6f}",
                f"{item['response_time_rel']:.6f}",
                f"{item['rtt']:.6f}",
                item["request_size"], item["response_size"]
            ])


# ----------------------------
# Dispatcher
# ----------------------------
def dispatcher(pcap_path, task_q):
    with open(pcap_path, "rb") as f:
        pcap = dpkt.pcap.Reader(f)
        for ts, buf in pcap:
            task_q.put((ts, buf))


# ----------------------------
# Main
# ----------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--input", required=True)
    parser.add_argument("-o", "--output", required=True)
    parser.add_argument("-w", "--workers", type=int, default=max(1, mp.cpu_count() - 1))
    args = parser.parse_args()

    task_q = mp.Queue(20000)
    result_q = mp.Queue()

    # Start aggregator
    agg = Process(target=aggregator_main, args=(result_q, args.output, args.workers))
    agg.start()

    # Start workers
    workers = []
    for _ in range(args.workers):
        p = Process(target=worker_main, args=(task_q, result_q, False))
        p.start()
        workers.append(p)

    # Feed packets
    dispatcher(args.input, task_q)

    # Stop workers
    for _ in workers:
        task_q.put("STOP")

    for p in workers:
        p.join()

    agg.join()

    print(f"[+] Done! Packets processed: {progress.value:,}")
    print(f"[+] Output written to: {args.output}")


if __name__ == "__main__":
    main()
