#!/usr/bin/env python3
import argparse
import multiprocessing
import csv
import dpkt
import socket
from multiprocessing import Value, Lock, Queue, Process
from collections import defaultdict

PRINT_INTERVAL = 100000

# ============================================================
# GLOBAL SHARED PROGRESS COUNTER
# ============================================================

progress = Value('i', 0)
progress_lock = Lock()


def update_progress():
    """Increment global progress every packet, print every PRINT_INTERVAL."""
    with progress_lock:
        progress.value += 1
        if progress.value % PRINT_INTERVAL == 0:
            print(f"[+] Processed {progress.value:,} packets...")


# ============================================================
# NORMALIZE IRCTC POST API URIs
# ============================================================

def normalize_irctc_uri(uri: str) -> str:
    """
    Normalizes IRCTC API URIs by reducing variable segments.
    Converts:
        /eticketing/.../avlFarenquiry/<train>/<date>/<src>/<dst>/<cls>/...
    Into:
        /eticketing/avlFarenquiry
    """

    if not uri:
        return uri

    parts = [p for p in uri.split("/") if p]
    if len(parts) < 3:
        return uri

    # Match API keywords
    for p in parts:
        low = p.lower()
        if low in (
            "avlfarenquiry",
            "avlfareenquiry",
            "fareenquiry",
            "fareenq",
            "avlfrq"
        ):
            return "/eticketing/avlFarenquiry"

    # Fallback default: first 3 segments
    return "/" + "/".join(parts[:3])


# ============================================================
# WORKER FUNCTION
# ============================================================

def worker_process(queue: Queue, result_q: Queue):
    local_counter = defaultdict(int)
    local_example = {}

    while True:
        item = queue.get()
        if item == "STOP":
            break

        ts, buf = item
        try:
            eth = dpkt.ethernet.Ethernet(buf)
            if not isinstance(eth.data, dpkt.ip.IP):
                update_progress()
                continue

            ip = eth.data

            if isinstance(ip.data, dpkt.tcp.TCP):
                tcp = ip.data

                # Skip if no data
                if len(tcp.data) == 0:
                    update_progress()
                    continue

                try:
                    http = dpkt.http.Request(tcp.data)
                except Exception:
                    update_progress()
                    continue

                if http.method != "POST":
                    update_progress()
                    continue

                uri = http.uri
                norm_uri = normalize_irctc_uri(uri)

                fp = f"POST {norm_uri}"
                local_counter[fp] += 1

                if fp not in local_example:
                    local_example[fp] = uri

        except Exception:
            pass

        update_progress()

    # Push worker results
    result_q.put((local_counter, local_example))


# ============================================================
# MAIN PARSER (STREAM PCAP)
# ============================================================

def process_pcap_parallel(pcap_file, workers):
    queue = Queue(maxsize=5000)
    result_q = Queue()

    procs = []

    for _ in range(workers):
        p = Process(target=worker_process, args=(queue, result_q))
        p.start()
        procs.append(p)

    print(f"[+] Reading PCAP in streaming mode with {workers} workers...")

    # Stream packets
    with open(pcap_file, "rb") as f:
        pcap = dpkt.pcap.Reader(f)
        for ts, buf in pcap:
            queue.put((ts, buf))

    # Signal workers to stop
    for _ in range(workers):
        queue.put("STOP")

    # Collect results
    final_counts = defaultdict(int)
    final_examples = {}

    for _ in range(workers):
        counts, examples = result_q.get()
        for k, v in counts.items():
            final_counts[k] += v
        for k, v in examples.items():
            if k not in final_examples:
                final_examples[k] = v

    for p in procs:
        p.join()

    print(f"[+] Finished streaming. Total packets processed: {progress.value:,}")

    return final_counts, final_examples


# ============================================================
# WRITE CSV
# ============================================================

def write_csv(out_csv, counters, examples):
    with open(out_csv, "w", newline='', encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["normalized_api", "count", "example_original_uri"])

        for fp, count in sorted(counters.items(), key=lambda x: -x[1]):
            w.writerow([fp, count, examples.get(fp, "")])

    print(f"[+] CSV saved: {out_csv}")


# ============================================================
# MAIN
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Parallel POST Request Fingerprinter with IRCTC URI Normalization")
    parser.add_argument("-i", "--input", required=True, help="Input PCAP file")
    parser.add_argument("-o", "--out", default="post_request_summary.csv", help="Output CSV file")

    args = parser.parse_args()

    available = multiprocessing.cpu_count()
    workers = max(1, available - 1)

    print(f"[+] CPU cores: {available}, using workers: {workers}")

    counters, examples = process_pcap_parallel(args.input, workers)
    write_csv(args.out, counters, examples)

    print("[+] Done.")


if __name__ == "__main__":
    main()
