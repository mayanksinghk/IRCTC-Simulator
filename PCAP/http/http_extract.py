#!/usr/bin/env python3
import dpkt
import socket
import multiprocessing as mp
import os
import sys
from queue import Empty

# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def inet_to_str(x):
    try:
        return socket.inet_ntop(socket.AF_INET, x)
    except:
        return None

def parse_http(data):
    """Try parsing as HTTP request or response."""
    try:
        req = dpkt.http.Request(data)
        return ("request", req.method, None)
    except:
        pass

    try:
        resp = dpkt.http.Response(data)
        return ("response", None, resp.reason)
    except:
        pass

    return None


# ------------------------------------------------------------
# Worker
# ------------------------------------------------------------
def worker_main(task_q, out_q, wid):
    while True:
        try:
            item = task_q.get(timeout=1)
        except Empty:
            continue

        if item is None:
            break

        ts_rel, eth_data = item

        try:
            eth = dpkt.ethernet.Ethernet(eth_data)
        except:
            continue

        if not isinstance(eth.data, dpkt.ip.IP):
            continue
        ip = eth.data

        if not isinstance(ip.data, dpkt.tcp.TCP):
            continue
        tcp = ip.data

        if len(tcp.data) == 0:
            continue

        # Only HTTP by port heuristic
        http_ports = {80, 8080, 8000, 8888}
        if tcp.dport not in http_ports and tcp.sport not in http_ports:
            continue

        parsed = parse_http(tcp.data)
        if not parsed:
            continue

        direction, method, reason = parsed

        client = f"{inet_to_str(ip.src)}:{tcp.sport}"
        server = f"{inet_to_str(ip.dst)}:{tcp.dport}"

        # If HTTP response → reverse direction
        if direction == "response":
            client, server = server, client

        pkt_len = len(tcp.data)

        out_q.put((ts_rel, client, server, pkt_len, method, reason, direction))

    out_q.put(("DONE", wid))
    return


# ------------------------------------------------------------
# Writer (also generates summary)
# ------------------------------------------------------------
def writer_main(out_q, out_req, out_res, total_workers):
    done = 0
    req_count = {}
    res_count = {}

    with open(out_req, "w") as fw_req, open(out_res, "w") as fw_res:
        while True:
            try:
                item = out_q.get(timeout=2)
            except Empty:
                continue

            if item[0] == "DONE":
                done += 1
                print(f"[INFO] Worker {item[1]} exited ({done}/{total_workers})")
                if done == total_workers:
                    break
                continue

            ts_rel, client, server, pkt_len, method, reason, direction = item

            if direction == "request":
                fw_req.write(f"{ts_rel:.6f}  {client} -> {server}  {pkt_len}  {method}\n")
                req_count[method] = req_count.get(method, 0) + 1

            else:  # response
                fw_res.write(f"{ts_rel:.6f}  {client} -> {server}  {pkt_len}  {reason}\n")
                res_count[reason] = res_count.get(reason, 0) + 1

    # Write summary file
    with open(out_res + "_summary.txt", "w") as fs:
        fs.write("=== HTTP REQUEST SUMMARY ===\n")
        for m, c in req_count.items():
            fs.write(f"{m}: {c}\n")

        fs.write("\n=== HTTP RESPONSE SUMMARY ===\n")
        for r, c in res_count.items():
            fs.write(f"{r}: {c}\n")

    print("[INFO] Summary written.")
    print("[INFO] Writer done.")


# ------------------------------------------------------------
# Main
# ------------------------------------------------------------
def main(pcap_file, out_prefix):
    print(f"[INFO] Reading: {pcap_file}")

    out_req = out_prefix + "_client_to_server.txt"
    out_res = out_prefix + "_server_to_client.txt"

    workers = mp.cpu_count() - 1
    print(f"[INFO] Using {workers} workers")

    task_q = mp.Queue(maxsize=20000)
    out_q = mp.Queue()

    # Open PCAP
    try:
        f = open(pcap_file, "rb")
        pcap = dpkt.pcap.Reader(f)
    except Exception:
        print("[FATAL] PCAP-NG detected. Convert with:")
        print(f"  editcap -F libpcap {pcap_file} fixed.pcap")
        sys.exit(1)

    print("[INFO] Streaming packets...")

    # Determine first timestamp (for correct relative time)
    start_ts = None
    pkt_count = 0

    # Start writer
    writer = mp.Process(target=writer_main, args=(out_q, out_req, out_res, workers))
    writer.start()

    # Start workers
    pool = []
    for i in range(workers):
        p = mp.Process(target=worker_main, args=(task_q, out_q, i))
        p.start()
        pool.append(p)

    # Stream packets directly
    for ts, buf in pcap:
        pkt_count += 1
        if pkt_count % 100000 == 0:
            print(f"[INFO] {pkt_count} packets read...")

        if start_ts is None:
            start_ts = ts

        task_q.put((ts - start_ts, buf))

    print("[INFO] Finished reading PCAP. Sending shutdown signals...")

    # Shutdown workers
    for _ in range(workers):
        task_q.put(None)

    for p in pool:
        p.join()

    print("[INFO] Workers finished. Waiting for writer...")

    writer.join()

    print(f"[INFO] Output written:\n  {out_req}\n  {out_res}\n  {out_res}_summary.txt")


# ------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("-f", "--file", required=True)
    ap.add_argument("-o", "--out", required=True)
    args = ap.parse_args()

    main(args.file, args.out)
