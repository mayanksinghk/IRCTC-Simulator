#!/usr/bin/env python3
"""
http_fingerprint_parallel.py

Parallel streaming HTTP fingerprinting (Option A - full normalization).

Outputs:
 - unique_http_requests.csv
 - unique_http_responses.csv
 - summary.txt

Usage:
 python3 http_fingerprint_parallel.py -i input.pcap -o outdir -w 4 -v
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import ipaddress
import logging
import multiprocessing as mp
import queue
import re
import socket
import struct
import sys
import time
from collections import defaultdict, deque
from typing import Dict, Tuple, Optional

import dpkt

# ----------------------------
# Configurable constants
# ----------------------------
PACKET_LOG_EVERY = 100_000   # print every N packets globally
WORKER_QUEUE_MAXSIZE = 50_000
RESULT_QUEUE_MAXSIZE = 200_000
FLOW_BUFFER_LIMIT = 5_000_000  # bytes per flow before we drop oldest data
SNIPPET_LEN = 800              # bytes stored as example
MASK_LONG_NUM_DIGITS = 5       # sequences of digits >= this replaced by <ID>
MASK_LONG_HEX_CHARS = 8        # sequences of hex chars >= this replaced by <HEXID>

# ----------------------------
# Helpers for normalization
# ----------------------------
_DIGITS_RE = re.compile(r'\d{' + str(MASK_LONG_NUM_DIGITS) + r',}')
_HEXLONG_RE = re.compile(r'\b[0-9a-fA-F]{' + str(MASK_LONG_HEX_CHARS) + r',}\b')
_MULTIWS = re.compile(r'\s+')
_URL_QUERY_RE = re.compile(r'([^\?]+)\?.*')  # capture path before query

def mask_ids(s: str) -> str:
    """Replace long digit sequences and long hex-like sequences with placeholders."""
    s = _HEXLONG_RE.sub('<HEXID>', s)
    s = _DIGITS_RE.sub('<ID>', s)
    return s

def normalize_headers(header_lines: str) -> str:
    """Take raw header block, return normalized header signature string."""
    # split, lowercase header names, sort them (names only), ignore header values (optionally)
    lines = [ln for ln in header_lines.split('\r\n') if ln.strip()]
    header_pairs = []
    for ln in lines:
        if ':' in ln:
            name, val = ln.split(':', 1)
            header_pairs.append(name.strip().lower())
        else:
            # continuation or weird line -> keep as-is
            header_pairs.append(ln.strip().lower())
    header_pairs = sorted(set(header_pairs))
    return '|'.join(header_pairs)

def normalize_request_startline(startline: str) -> Tuple[str, str, str]:
    """
    Parse and normalize request start line.
    Returns (method, path_no_query, proto)
    """
    parts = startline.strip().split()
    if len(parts) < 2:
        return (startline.strip().lower(), "", "")
    method = parts[0].upper()
    path = parts[1]
    m = _URL_QUERY_RE.match(path)
    if m:
        path = m.group(1)
    # remove trailing multiple slashes, collapse digits/hexIDs
    path = mask_ids(path)
    return (method, path, parts[2] if len(parts) >= 3 else "")

def normalize_response_startline(startline: str) -> Tuple[str, str]:
    """
    Parse response status line.
    Returns (status_code, proto)
    """
    parts = startline.strip().split()
    if len(parts) < 2:
        return ("", "")
    proto = parts[0]
    status = parts[1]
    return (status, proto)

def make_fingerprint_from_parts(parts: bytes) -> str:
    """Return sha256 hex digest of bytes"""
    h = hashlib.sha256()
    h.update(parts)
    return h.hexdigest()

def extract_headers_and_body(buffer: bytes) -> Tuple[Optional[str], Optional[str], Optional[bytes]]:
    """
    Split buffer into start-line, header-block, and remaining body (if any).
    Returns (startline, header_block, body_bytes or None if headers not complete)
    """
    try:
        buf = buffer
        idx = buf.find(b'\r\n\r\n')
        if idx == -1:
            return None, None, None
        header_block = buf[:idx].decode('latin1', errors='replace')
        rest = buf[idx + 4:]
        # first line is startline
        lines = header_block.split('\r\n')
        startline = lines[0] if lines else ''
        return startline, header_block, rest
    except Exception:
        return None, None, None

# ----------------------------
# TCP reassembly per flow (basic)
# ----------------------------
class FlowReassembler:
    """
    Simple seq-based reassembler for TCP flows.
    Keyed by 4-tuple (src_ip, src_port, dst_ip, dst_port).
    Maintains a dict of (seq -> data) and attempts to produce contiguous bytes.
    """

    def __init__(self):
        # maps flow -> dict of seq->data (only for outstanding fragments)
        self.fragments: Dict[Tuple[str,int,str,int], Dict[int, bytes]] = {}
        # maps flow -> next expected sequence (lowest contiguous seq available)
        self.next_seq: Dict[Tuple[str,int,str,int], Optional[int]] = {}
        # maps flow -> deque of assembled bytes (we use a bytearray to accumulate)
        self.buffers: Dict[Tuple[str,int,str,int], bytearray] = {}

    @staticmethod
    def _flow_key(src_ip: bytes, sport: int, dst_ip: bytes, dport: int) -> Tuple[str,int,str,int]:
        return (socket.inet_ntoa(src_ip), sport, socket.inet_ntoa(dst_ip), dport)

    def add_segment(self, src_ip: bytes, sport: int, dst_ip: bytes, dport: int, seq: int, data: bytes):
        key = self._flow_key(src_ip, sport, dst_ip, dport)
        frags = self.fragments.setdefault(key, {})
        if not data:
            return key
        # Avoid storing duplicates for exact seq
        if seq in frags:
            # If identical, ignore
            if frags[seq] == data:
                return key
            # otherwise keep the larger / newer? We'll prefer the first seen to keep deterministic.
            return key
        frags[seq] = data
        # init buffer/next_seq
        if key not in self.buffers:
            self.buffers[key] = bytearray()
        if key not in self.next_seq:
            # set next_seq to seq (we don't know syn/ISN), so we pick min existing seq when extracting
            self.next_seq[key] = None
        return key

    def try_assemble(self, key) -> bytes:
        """
        Try to merge fragments into contiguous bytes starting from smallest seq if next_seq is None,
        or from next_seq if set. Returns assembled bytes (could be empty).
        """
        if key not in self.fragments:
            return b''

        frags = self.fragments[key]
        if not frags:
            return b''

        # choose starting seq
        if self.next_seq[key] is None:
            # pick smallest seq as starting point
            start_seq = min(frags.keys())
            self.next_seq[key] = start_seq
        else:
            start_seq = self.next_seq[key]

        assembled = bytearray()
        cur = start_seq
        changed = True
        while True:
            if cur in frags:
                chunk = frags.pop(cur)
                assembled.extend(chunk)
                cur += len(chunk)
                # continue loop
            else:
                break

        # update next_seq
        if assembled:
            self.next_seq[key] = cur
            # append to buffer
            self.buffers[key].extend(assembled)
            # enforce buffer size limit
            if len(self.buffers[key]) > FLOW_BUFFER_LIMIT:
                # drop oldest bytes to keep memory in check
                excess = len(self.buffers[key]) - FLOW_BUFFER_LIMIT
                del self.buffers[key][:excess]
            return bytes(assembled)
        return b''

    def consume_from_buffer(self, key, nbytes) -> bytes:
        """Pop first nbytes from assembled buffer (if available)."""
        buf = self.buffers.get(key)
        if not buf:
            return b''
        n = min(nbytes, len(buf))
        res = bytes(buf[:n])
        del buf[:n]
        return res

    def peek_buffer(self, key) -> bytes:
        b = self.buffers.get(key)
        return bytes(b) if b else b''

    def discard_flow(self, key):
        self.fragments.pop(key, None)
        self.next_seq.pop(key, None)
        self.buffers.pop(key, None)

# ----------------------------
# Worker: receives (ts, raw_pkt) via input_queue, processes, and sends fingerprint events to result_queue.
# ----------------------------
def worker_main(worker_id: int, input_queue: mp.Queue, result_queue: mp.Queue,
                prog_queue: mp.Queue, verbose: bool):
    logger = logging.getLogger(f"worker-{worker_id}")
    reasm = FlowReassembler()
    processed = 0
    req_count = 0
    resp_count = 0

    try:
        while True:
            try:
                item = input_queue.get()
            except Exception:
                break
            if item is None:
                break  # poison
            ts, buf = item
            processed += 1
            # report progress aggregated
            if proc_safe_put(prog_queue, 1) is False:
                # queue full; ignore
                pass

            try:
                eth = dpkt.ethernet.Ethernet(buf)
                if not isinstance(eth.data, dpkt.ip.IP):
                    continue
                ip = eth.data
                if not isinstance(ip.data, dpkt.tcp.TCP):
                    continue
                tcp = ip.data
                payload = tcp.data
                if not payload:
                    continue

                # Add segment into reassembler keyed by 4-tuple (src->dst)
                key = reasm.add_segment(ip.src, tcp.sport, ip.dst, tcp.dport, tcp.seq, payload)
                # Try to assemble contiguous bytes
                _ = reasm.try_assemble(key)
                # Peek the buffer for this direction
                buff = reasm.peek_buffer(key)
                # Try to extract HTTP messages (requests or responses) from buffer
                while True:
                    startline, headers_block, rest = extract_headers_and_body(buff)
                    if startline is None:
                        # headers incomplete
                        break
                    # Determine if request or response
                    is_request = False
                    is_response = False
                    sline = startline.strip()
                    # crude: if starts with HTTP/ => response
                    if sline.startswith('HTTP/'):
                        is_response = True
                    else:
                        # request: METHOD PATH PROTO; methods are common uppercase words
                        # check for uppercase METHOD tokens
                        if re.match(r'^[A-Z]+ ', sline):
                            is_request = True
                        else:
                            # uncertain -> treat as request if contains 'GET' or 'POST' at start
                            if sline.split()[0] in ('GET','POST','PUT','HEAD','OPTIONS','DELETE','PATCH'):
                                is_request = True

                    # Determine required body length (if any)
                    headers_lines = headers_block.split('\r\n')[1:]  # skip startline
                    header_map = {}
                    for ln in headers_lines:
                        if ':' in ln:
                            n,v = ln.split(':',1)
                            header_map[n.strip().lower()] = v.strip()
                    content_len = None
                    if 'content-length' in header_map:
                        try:
                            content_len = int(re.sub(r'\D','', header_map['content-length']) or 0)
                        except Exception:
                            content_len = None
                    # For chunked, we won't attempt to fully assemble body. We'll fingerprint with header + small body snippet.

                    # Check whether full body present
                    body_needed = content_len if content_len is not None else 0
                    if len(rest) < body_needed:
                        # wait for more bytes
                        break

                    # We have headers (+ possibly full body). Extract full_message bytes for fingerprint snippet
                    full_msg_len = len(headers_block.encode('latin1')) + 4 + min(len(rest), max(0, body_needed))
                    # We'll take header+first SNIPPET_LEN of body for fingerprint/example
                    example_bytes = buff[:4 + len(headers_block.encode('latin1')) + min(len(rest), SNIPPET_LEN)]
                    # Build normalized fingerprint
                    try:
                        if is_request:
                            method, path, proto = normalize_request_startline(startline)
                            normalized = method + ' ' + path + ' ' + proto + '\n'
                            normalized += normalize_headers(headers_block)
                            # include small body snippet (masked)
                            if rest:
                                body_snip = rest[:512].decode('latin1', errors='replace')
                                normalized += '\n' + mask_ids(_MULTIWS.sub(' ', body_snip)).lower()
                            else:
                                normalized += '\n'
                            normalized = mask_ids(normalized)
                            sha = make_fingerprint_from_parts(normalized.encode('utf8'))
                            proc_safe_put(result_queue, ('REQ', sha, example_bytes.decode('latin1', errors='replace')))
                            req_count += 1
                        elif is_response:
                            status, proto = normalize_response_startline(startline)
                            normalized = status + ' ' + proto + '\n'
                            normalized += normalize_headers(headers_block)
                            if rest:
                                body_snip = rest[:512].decode('latin1', errors='replace')
                                normalized += '\n' + mask_ids(_MULTIWS.sub(' ', body_snip)).lower()
                            else:
                                normalized += '\n'
                            normalized = mask_ids(normalized)
                            sha = make_fingerprint_from_parts(normalized.encode('utf8'))
                            proc_safe_put(result_queue, ('RESP', sha, example_bytes.decode('latin1', errors='replace')))
                            resp_count += 1
                        else:
                            # unknown, skip
                            pass
                    except Exception:
                        # ignore fingerprint errors
                        pass

                    # consume the bytes from buffer corresponding to this message
                    # if content_len known: consume header + 4 + content_len, else consume header only (for requests like GET)
                    consume_len = 4 + len(headers_block.encode('latin1')) + (body_needed if body_needed is not None else 0)
                    # But if body_needed was None -> we only consume headers (safe)
                    if body_needed is None:
                        consume_len = 4 + len(headers_block.encode('latin1'))
                    # ensure we do not over-consume
                    available = len(reasm.peek_buffer(key))
                    if consume_len > available:
                        # fallback: consume headers only
                        consume_len = 4 + len(headers_block.encode('latin1'))
                    _ = reasm.consume_from_buffer(key, consume_len)
                    # update buff for while-loop
                    buff = reasm.peek_buffer(key)

                # end while trying to extract messages
            except Exception:
                # ignore malformed frames
                continue

            if verbose and (processed % PACKET_LOG_EVERY == 0):
                logger.info(f"processed {processed:,} packets; reqs={req_count}, resps={resp_count}")

    except KeyboardInterrupt:
        pass
    finally:
        # send a DONE signal and a final stats message
        try:
            proc_safe_put(result_queue, ('WORKER_DONE', worker_id, req_count, resp_count))
        except Exception:
            pass
        if verbose:
            logger.info(f"worker exiting processed={processed} reqs={req_count} resps={resp_count}")

def proc_safe_put(q: mp.Queue, item):
    """Try to put into mp.Queue without blocking (returns False if fails)."""
    try:
        q.put(item, block=False)
        return True
    except Exception:
        # queue full or closed
        try:
            q.put(item, block=True, timeout=0.1)
            return True
        except Exception:
            return False

# ----------------------------
# Dispatcher: read pcap and round-robin to worker queues
# ----------------------------
def dispatcher_main(pcap_path: str, worker_queues: list, prog_queue: mp.Queue, verbose: bool):
    logger = logging.getLogger("dispatcher")
    total = 0
    wcount = len(worker_queues)
    rr = 0
    try:
        with open(pcap_path, "rb") as fh:
            pcap = dpkt.pcap.Reader(fh)
            for ts, buf in pcap:
                # put to worker rr
                q = worker_queues[rr]
                # try to enqueue; if full, block briefly (backpressure)
                while True:
                    try:
                        q.put((ts, buf), block=True, timeout=1.0)
                        break
                    except queue.Full:
                        time.sleep(0.01)
                total += 1
                rr = (rr + 1) % wcount
                if total % PACKET_LOG_EVERY == 0 and verbose:
                    logger.info(f"[dispatcher] streamed {total:,} packets")
                # also aggregate to prog_queue for global counting (workers also push, but dispatcher counts too)
                proc_safe_put(prog_queue, 0)  # dummy to ensure monitor is active
    except Exception as e:
        logger.error(f"dispatcher exception: {e}")
    finally:
        # send poison pill to workers
        for q in worker_queues:
            q.put(None)
        if verbose:
            logger.info(f"dispatcher finished, total streamed={total:,}")

# ----------------------------
# Result aggregator: collects fingerprint events and writes outputs at the end
# ----------------------------
def aggregator_main(result_queue: mp.Queue, n_workers: int, out_dir: str, verbose: bool):
    logger = logging.getLogger("aggregator")
    req_counts: Dict[str, int] = defaultdict(int)
    resp_counts: Dict[str, int] = defaultdict(int)
    req_examples: Dict[str, str] = {}
    resp_examples: Dict[str, str] = {}

    workers_done = 0
    total_events = 0
    start_time = time.time()

    while workers_done < n_workers:
        try:
            item = result_queue.get(timeout=5.0)
        except Exception:
            # timeout -> loop and check
            continue
        if not item:
            continue
        typ = item[0]
        if typ == 'REQ':
            _, sha, example = item
            req_counts[sha] += 1
            if sha not in req_examples:
                req_examples[sha] = example[:SNIPPET_LEN]
            total_events += 1
        elif typ == 'RESP':
            _, sha, example = item
            resp_counts[sha] += 1
            if sha not in resp_examples:
                resp_examples[sha] = example[:SNIPPET_LEN]
            total_events += 1
        elif typ == 'WORKER_DONE':
            _, worker_id, rc, pc = item
            workers_done += 1
            if verbose:
                logger.info(f"aggregator: worker {worker_id} done (reqs={rc} resps={pc}) [{workers_done}/{n_workers}]")
        else:
            # unexpected message type
            pass

    # write CSV outputs
    req_csv = f"{out_dir}/unique_http_requests.csv"
    resp_csv = f"{out_dir}/unique_http_responses.csv"

    # -----------------------------
    # SAFE CSV WRITER CONFIG
    # -----------------------------
    def make_writer(fh):
        return csv.writer(
            fh,
            delimiter=',',
            quotechar='"',
            quoting=csv.QUOTE_ALL,   # <-- CRITICAL: ensure no escaping errors
            escapechar='\\',
            lineterminator='\n'
        )

    # -----------------------------
    # WRITE REQUESTS
    # -----------------------------
    with open(req_csv, "w", newline='', encoding='utf8') as fh:
        w = make_writer(fh)
        w.writerow(['sha256', 'count', 'example_snippet'])

        for sha, cnt in sorted(req_counts.items(), key=lambda x: -x[1]):
            snippet = req_examples.get(sha, '')
            w.writerow([sha, cnt, snippet])

    # -----------------------------
    # WRITE RESPONSES
    # -----------------------------
    with open(resp_csv, "w", newline='', encoding='utf8') as fh:
        w = make_writer(fh)
        w.writerow(['sha256', 'count', 'example_snippet'])

        for sha, cnt in sorted(resp_counts.items(), key=lambda x: -x[1]):
            snippet = resp_examples.get(sha, '')
            w.writerow([sha, cnt, snippet])


    # write summary
    summary_file = f"{out_dir}/summary.txt"
    total_reqs = sum(req_counts.values())
    total_resps = sum(resp_counts.values())
    unique_reqs = len(req_counts)
    unique_resps = len(resp_counts)
    with open(summary_file, "w", encoding='utf8') as fh:
        fh.write(f"Processing summary\n")
        fh.write(f"==================\n")
        fh.write(f"Total fingerprint events: {total_events}\n")
        fh.write(f"Total requests: {total_reqs}\n")
        fh.write(f"Total responses: {total_resps}\n")
        fh.write(f"Unique request fingerprints: {unique_reqs}\n")
        fh.write(f"Unique response fingerprints: {unique_resps}\n")
        fh.write("\nTop 20 request fingerprints:\n")
        for sha, cnt in sorted(req_counts.items(), key=lambda x: -x[1])[:20]:
            fh.write(f"{cnt:10d}  {sha}\n")
        fh.write("\nTop 20 response fingerprints:\n")
        for sha, cnt in sorted(resp_counts.items(), key=lambda x: -x[1])[:20]:
            fh.write(f"{cnt:10d}  {sha}\n")
    if verbose:
        logger.info(f"Wrote outputs: {req_csv}, {resp_csv}, {summary_file}")
    return req_csv, resp_csv, summary_file

# ----------------------------
# Progress monitor: aggregate totals from prog_queue and print every PACKET_LOG_EVERY
# ----------------------------
def progress_monitor(prog_queue: mp.Queue, stop_event: mp.Event, verbose: bool):
    total = 0
    last_print = 0
    logger = logging.getLogger("progress")
    while not stop_event.is_set():
        try:
            item = prog_queue.get(timeout=1.0)
        except Exception:
            continue
        # items are integers (1) from workers or 0 padders
        try:
            total += int(item)
        except Exception:
            pass
        if verbose and (total - last_print) >= PACKET_LOG_EVERY:
            logger.info(f"[global] processed {total:,} packets")
            last_print = total
    # final print
    if verbose:
        logger.info(f"[global] final processed {total:,} packets (monitor exiting)")

# ----------------------------
# Main entrypoint orchestration
# ----------------------------
def main():
    p = argparse.ArgumentParser(description="Parallel streaming HTTP fingerprinting (Option A)")
    p.add_argument("-i", "--input", required=True, help="Input PCAP file")
    p.add_argument("-o", "--outdir", required=True, help="Output directory (will be created)")
    p.add_argument("-w", "--workers", type=int, default=max(mp.cpu_count() - 1, 1),
                   help="Number of worker processes (default: CPU-1)")
    p.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")
    args = p.parse_args()

    import os
    os.makedirs(args.outdir, exist_ok=True)

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s",
                        datefmt="%H:%M:%S")
    logger = logging.getLogger("main")

    # Create queues and worker processes
    manager = mp.Manager()
    worker_queues = [manager.Queue(maxsize=WORKER_QUEUE_MAXSIZE) for _ in range(args.workers)]
    result_queue = manager.Queue(maxsize=RESULT_QUEUE_MAXSIZE)
    prog_queue = manager.Queue()
    stop_event = mp.Event()

    workers = []
    for i in range(args.workers):
        pproc = mp.Process(target=worker_main, args=(i+1, worker_queues[i], result_queue, prog_queue, args.verbose))
        pproc.start()
        workers.append(pproc)

    # Start progress monitor
    prog_mon = mp.Process(target=progress_monitor, args=(prog_queue, stop_event, args.verbose))
    prog_mon.start()

    # Start dispatcher in main thread (it will stream and push packets to worker queues)
    logger.info(f"Starting dispatcher -> streaming PCAP to {len(worker_queues)} workers")
    dispatcher_main(args.input, worker_queues, prog_queue, args.verbose)

    # Wait for workers to finish
    logger.info("Waiting for workers to finish...")
    for pproc in workers:
        pproc.join()

    # workers are done; now aggregate results
    logger.info("Aggregating results...")
    req_csv, resp_csv, summary_file = aggregator_main(result_queue, args.workers, args.outdir, args.verbose)

    # stop progress monitor
    stop_event.set()
    try:
        prog_queue.put(0)
    except Exception:
        pass
    prog_mon.join(timeout=2.0)

    logger.info("Done.")
    logger.info(f"Outputs: {req_csv}, {resp_csv}, {summary_file}")

if __name__ == "__main__":
    main()
