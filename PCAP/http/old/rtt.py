#!/usr/bin/env python3
import pyshark
import multiprocessing as mp
import argparse
import time
import csv
from queue import Empty
import shutil
import sys
import math

CPU_CORES = max(1, mp.cpu_count() - 1)
CHUNK_SIZE = 8000  # how many packets per batch to workers


###############################################################################
# ---------------------------  Helper: Progress Bar  --------------------------
###############################################################################

def print_progress(processed, total, start_time):
    if total <= 0:
        return

    percent = processed / total
    bar_len = shutil.get_terminal_size().columns - 40
    bar_len = max(10, bar_len)

    filled = int(bar_len * percent)
    bar = "#" * filled + "-" * (bar_len - filled)

    elapsed = time.time() - start_time
    if processed > 0:
        rate = processed / elapsed
        remaining = (total - processed) / rate
    else:
        remaining = 0

    eta = time.strftime("%H:%M:%S", time.gmtime(remaining))

    sys.stdout.write(
        f"\r[{bar}]  {percent*100:5.1f}%  ETA:{eta}"
    )
    sys.stdout.flush()


###############################################################################
# ---------------------------  Worker Function  -------------------------------
###############################################################################

def worker_process(worker_id, work_q, result_q):
    print(f"[WORKER-{worker_id}] Started")

    pending = {}  # key: (4-tuple flow, method, uri) → request_time
    matched_count = 0

    while True:
        try:
            chunk = work_q.get(timeout=3)
        except Empty:
            continue

        if chunk is None:
            print(f"[WORKER-{worker_id}] Exiting")
            break

        result_rows = []

        for p in chunk:
            # REQUEST
            if p["type"] == "request":
                key = (
                    (p["src"], p["sport"], p["dst"], p["dport"]),
                    p["method"],
                    p["uri"]
                )
                pending[key] = p["time"]

            # RESPONSE
            elif p["type"] == "response":
                flow_rev = (p["dst"], p["dport"], p["src"], p["sport"])

                found = False
                for (req_flow, method, uri), req_time in list(pending.items()):
                    if req_flow == flow_rev:
                        rtt = p["time"] - req_time
                        result_rows.append([
                            req_flow[0], req_flow[1], req_flow[2], req_flow[3],
                            method, uri,
                            req_time, p["time"],
                            p["code"], rtt
                        ])
                        del pending[(req_flow, method, uri)]
                        matched_count += 1
                        found = True
                        break

                if not found:
                    pass  # unmatched response (normal in WAF logs)

        result_q.put(result_rows)

    result_q.put({"worker_done": True, "matched": matched_count})
    print(f"[WORKER-{worker_id}] Finished")


###############################################################################
# ---------------------------  MAIN STREAMING PCAP  ---------------------------
###############################################################################

def stream_pcap(file_path, output_csv, total_packets):

    print(f"[MASTER] Spawning {CPU_CORES} workers")

    manager = mp.Manager()
    work_q = manager.Queue(maxsize=CPU_CORES * 3)
    result_q = manager.Queue()

    workers = []
    for i in range(CPU_CORES):
        p = mp.Process(target=worker_process, args=(i, work_q, result_q))
        p.start()
        workers.append(p)

    print("[MASTER] Worker processes started\n")

    cap = pyshark.FileCapture(
        file_path,
        keep_packets=False,
        decode_as={'tcp.port==80': 'http'},
        use_json=True
    )

    buffer = []
    chunk_id = 0
    pkt_count = 0
    http_count = 0

    t0 = time.time()

    # CSV writer
    f = open(output_csv, "w", newline="")
    writer = csv.writer(f)
    writer.writerow([
        "src_ip", "src_port", "dst_ip", "dst_port",
        "method", "uri",
        "request_time", "response_time",
        "status", "rtt"
    ])

    # Result handling
    completed_workers = 0
    total_matched = 0

    print("[MASTER] Starting packet stream...\n")

    for pkt in cap:
        pkt_count += 1

        if total_packets:
            print_progress(pkt_count, total_packets, t0)

        try:
            ptime = float(pkt.sniff_timestamp)
        except:
            continue

        if 'HTTP' not in pkt:
            continue

        http_count += 1

        try:
            src = pkt.ip.src
            dst = pkt.ip.dst
            sport = pkt.tcp.srcport
            dport = pkt.tcp.dstport
        except:
            continue

        # request
        if hasattr(pkt.http, "request_method"):
            buffer.append({
                "type": "request",
                "src": src,
                "dst": dst,
                "sport": sport,
                "dport": dport,
                "method": pkt.http.request_method,
                "uri": getattr(pkt.http, "request_uri", ""),
                "time": ptime
            })

        # response
        elif hasattr(pkt.http, "response_code"):
            buffer.append({
                "type": "response",
                "src": src,
                "dst": dst,
                "sport": sport,
                "dport": dport,
                "code": pkt.http.response_code,
                "time": ptime
            })

        if len(buffer) >= CHUNK_SIZE:
            work_q.put(buffer)
            buffer = []
            chunk_id += 1

        # Process any available results
        try:
            while True:
                res = result_q.get_nowait()
                if isinstance(res, dict) and "worker_done" in res:
                    completed_workers += 1
                    total_matched += res["matched"]
                else:
                    for row in res:
                        writer.writerow(row)
        except Empty:
            pass

    # Last chunk
    if buffer:
        work_q.put(buffer)

    # Stop workers
    for _ in workers:
        work_q.put(None)

    print("\n[MASTER] Waiting for workers to finish...")

    while completed_workers < CPU_CORES:
        try:
            res = result_q.get(timeout=3)
            if isinstance(res, dict) and "worker_done" in res:
                completed_workers += 1
                total_matched += res["matched"]
            else:
                for row in res:
                    writer.writerow(row)
        except Empty:
            pass

    f.close()

    elapsed = time.time() - t0

    print("\n============================================")
    print("                SUMMARY")
    print("============================================")
    print(f"Total packets read:         {pkt_count}")
    print(f"Total HTTP packets:         {http_count}")
    print(f"Total matched pairs:        {total_matched}")
    print(f"Total time taken:           {elapsed:.2f} sec")
    print("============================================\n")


###############################################################################
# ---------------------------  ARGUMENT PARSER  -------------------------------
###############################################################################

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="HTTP RTT Extractor")
    parser.add_argument("-f", "--file", required=True, help="input pcap")
    parser.add_argument("-o", "--output", required=True, help="output csv")
    parser.add_argument("--total", type=int, default=0,
                        help="total packets (from tshark)")
    args = parser.parse_args()

    stream_pcap(args.file, args.output, args.total)
