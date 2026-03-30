#!/usr/bin/env python3
import subprocess
import glob
import concurrent.futures
import matplotlib.pyplot as plt
import numpy as np
import os
import gzip
import csv
import argparse
import urllib.parse

# --- CONFIGURATION ---
MAX_TIME_SECONDS = 2.0

def normalize_pattern(pat):
    """Decodes URL encoding and strips protocols for clean matching."""
    pat = urllib.parse.unquote(pat.strip())
    pat = pat.replace("http://", "").replace("https://", "")
    return pat

def extract_full_url_data(pcap_file, get_patterns, post_patterns):
    node_name = os.path.basename(pcap_file)
    print(f"[{node_name}] Processing...")
    
    cmd = [
        "tshark", "-r", pcap_file,
        "-Y", f"http.request or (http.time and http.time < {MAX_TIME_SECONDS})", 
        "-T", "fields",
        "-e", "tcp.stream",
        "-e", "http.request.method",
        "-e", "http.host",
        "-e", "http.request.uri",
        "-e", "http.time"
    ]
    
    local_storage = {
        "GET": {pat: [] for pat in get_patterns},
        "POST": {pat: [] for pat in post_patterns}
    }
    
    active_streams = {}
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        for line in process.stdout:
            parts = line.strip('\n').split('\t')
            if len(parts) >= 5:
                stream_id = parts[0].strip()
                method = parts[1].strip().upper()
                host = parts[2].strip()
                uri = parts[3].strip()
                rtt_str = parts[4].strip()
                
                if not stream_id:
                    continue

                if method in ["GET", "POST"]:
                    uri = urllib.parse.unquote(uri)
                    if uri.startswith("http://") or uri.startswith("https://"):
                        compare_url = uri.replace("http://", "").replace("https://", "")
                    else:
                        compare_url = f"{host}{uri}"
                        
                    active_streams[stream_id] = (method, compare_url)
                
                elif rtt_str and stream_id in active_streams:
                    try:
                        rtt = float(rtt_str.split(',')[0])
                        req_method, req_url = active_streams[stream_id]
                        
                        if req_method in local_storage:
                            for pattern in local_storage[req_method]:
                                if pattern in req_url:
                                    local_storage[req_method][pattern].append(rtt)
                        
                        del active_streams[stream_id]
                    except ValueError:
                        pass
    except Exception as e:
        print(f"Error on {pcap_file}: {e}")
        
    return local_storage

def save_and_plot_individual(data_map, method, output_root, min_matches):
    # Store everything directly in the GET or POST folder
    method_dir = os.path.join(output_root, method)
    os.makedirs(method_dir, exist_ok=True)
    
    for pattern, latencies in data_map.items():
        if not latencies:
            print(f"  > No data for {method} pattern: '{pattern[:50]}...'")
            continue
            
        # Check against the minimum matches threshold
        if len(latencies) < min_matches:
            print(f"  > Skipped: {method} - '{pattern[:50]}...' (Only {len(latencies)} samples, requires {min_matches})")
            continue
            
        safe_name = "".join([c if c.isalnum() else "_" for c in pattern])
        safe_name = safe_name[-100:] # Keep filename length reasonable
        
        # 1. Save CSV directly in the method folder
        csv_path = os.path.join(method_dir, f"latency_{safe_name}.csv.gz")
        with gzip.open(csv_path, 'wt', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['latency_seconds'])
            for lat in latencies:
                writer.writerow([lat])
        
        # 2. Plot Histogram (1ms Bins)
        plt.figure(figsize=(10, 6))
        
        # 0.001 seconds = 1ms buckets
        bins = np.arange(0, MAX_TIME_SECONDS + 0.001, 0.001) 
        
        # Removed 'edgecolor' so the 2,000 bins don't blur into a solid black box
        plt.hist(latencies, bins=bins, color='skyblue' if method == 'GET' else 'salmon')
        
        plt.title(f"{method} Latency Distribution (1ms Bins)\nPattern: {pattern[:60]}...", fontsize=10)
        plt.xlabel('Seconds')
        plt.ylabel('Frequency')
        plt.grid(axis='y', alpha=0.3)
        
        # Save image directly in the method folder
        plot_path = os.path.join(method_dir, f"dist_{safe_name}.png")
        plt.savefig(plot_path)
        plt.close()
        print(f"  > Success: {method} - '{pattern[:50]}...' ({len(latencies)} samples)")

def main():
    parser = argparse.ArgumentParser(description="Parallel Analysis with Stateful TCP Tracking (1ms Bins)")
    parser.add_argument("-i", "--input_dir", required=True)
    parser.add_argument("-o", "--output_dir", required=True)
    parser.add_argument("--get_list", required=True)
    parser.add_argument("--post_list", required=True)
    parser.add_argument("-m", "--min_matches", type=int, default=0, help="Minimum matches required to save/plot (default: 0)")
    
    args = parser.parse_args()
    
    with open(args.get_list, 'r') as f:
        get_pats = [normalize_pattern(l) for l in f if l.strip()]
    with open(args.post_list, 'r') as f:
        post_pats = [normalize_pattern(l) for l in f if l.strip()]
        
    pcap_files = glob.glob(os.path.join(args.input_dir, "*.pcap"))
    
    final_data = {
        "GET": {pat: [] for pat in get_pats},
        "POST": {pat: [] for pat in post_pats}
    }

    print(f"Starting parallel processing of {len(pcap_files)} files...")
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [executor.submit(extract_full_url_data, f, get_pats, post_pats) for f in pcap_files]
        for future in concurrent.futures.as_completed(futures):
            chunk_result = future.result()
            for method in ["GET", "POST"]:
                for pat in chunk_result[method]:
                    final_data[method][pat].extend(chunk_result[method][pat])

    print("\n--- Generating Plots and CSVs ---")
    save_and_plot_individual(final_data["GET"], "GET", args.output_dir, args.min_matches)
    save_and_plot_individual(final_data["POST"], "POST", args.output_dir, args.min_matches)

if __name__ == "__main__":
    main()