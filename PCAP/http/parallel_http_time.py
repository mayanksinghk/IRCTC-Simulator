#!/usr/bin/env python3
# This script processes multiple PCAP chunks in parallel to extract HTTP request-response times.
# It uses tshark to filter and extract relevant fields, then aggregates the data for analysis.
import subprocess
import glob
import concurrent.futures
import matplotlib.pyplot as plt
import numpy as np
import os
import gzip
import csv
import argparse

MAX_TIME_SECONDS = 2.0

def extract_http_time(pcap_file):
    """
    Worker function: Runs tshark on a single PCAP chunk.
    Extracts frame.time_relative and http.time.
    """
    print(f"[{os.path.basename(pcap_file)}] Started processing on CPU worker...")
    
    cmd = [
        "tshark", "-r", pcap_file,
        "-Y", f"http.time and http.time < {MAX_TIME_SECONDS}", 
        "-T", "fields",
        "-e", "frame.time_relative",
        "-e", "http.time"
    ]
    
    local_times = []
    local_req_res_times = []
    
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        
        for line in process.stdout:
            parts = line.strip().split('\t')
            if len(parts) >= 2:
                try:
                    time_val = float(parts[0].split(',')[0])
                    req_res_val = float(parts[1].split(',')[0])
                    
                    local_times.append(time_val)
                    local_req_res_times.append(req_res_val)
                except ValueError:
                    continue
                    
    except Exception as e:
        print(f"[{os.path.basename(pcap_file)}] Error: {e}")
        
    print(f"[{os.path.basename(pcap_file)}] Finished. Found {len(local_req_res_times)} packets.")
    return local_times, local_req_res_times

def export_to_csv_gz(times, req_res_times, output_dir):
    """Writes the aggregated data to a compressed CSV file in the output directory."""
    filename = os.path.join(output_dir, "http_request_response_times.csv.gz")
    print(f"\nExporting {len(times)} records to {filename}...")
    
    with gzip.open(filename, 'wt', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Relative_Time_Seconds', 'HTTP_Response_Time_Seconds'])
        writer.writerows(zip(times, req_res_times))
        
    print(f"Export complete. Data saved and compressed to '{filename}'.")

def plot_graphs(times, req_res_times, output_dir):
    """Generates the 3-panel figure and saves it to the output directory."""
    print("\nGenerating graphs for massive dataset. This may take a moment...")
    
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 18))
    fig.suptitle(f'HTTP Request-Response Time Analysis (< {MAX_TIME_SECONDS}s)', fontsize=16, y=0.92)
    
    # 1. Histogram (5ms bins)
    bins_5ms = np.arange(0, MAX_TIME_SECONDS + 0.005, 0.005)
    ax1.hist(req_res_times, bins=bins_5ms, color='skyblue', edgecolor='black', linewidth=0.5)
    ax1.set_title('Distribution (Histogram with 5ms bins)')
    ax1.set_xlabel('Time between Request and Response (Seconds)')
    ax1.set_ylabel('Frequency')
    ax1.set_xlim(0, MAX_TIME_SECONDS)
    ax1.grid(axis='y', alpha=0.75)
    
    # 2. Scatter Plot
    ax2.scatter(times, req_res_times, alpha=0.1, s=2, color='crimson')
    ax2.set_title('Request-Response Time over Capture Duration (Scatter)')
    ax2.set_xlabel('Time since capture start (Seconds)')
    ax2.set_ylabel('Time (Seconds)')
    ax2.set_ylim(0, MAX_TIME_SECONDS)
    ax2.grid(True, alpha=0.3)
    
    # 3. Latency Heatmap
    time_bins = 150 
    h = ax3.hist2d(times, req_res_times, bins=[time_bins, bins_5ms], cmap='viridis', cmin=1)
    ax3.set_title('Density Heatmap')
    ax3.set_xlabel('Time since capture start (Seconds)')
    ax3.set_ylabel('Time (Seconds)')
    ax3.set_ylim(0, MAX_TIME_SECONDS)
    
    cbar = fig.colorbar(h[3], ax=ax3)
    cbar.set_label('Packet Count Density')
    
    plt.tight_layout(rect=[0, 0.03, 1, 0.90])
    
    filepath = os.path.join(output_dir, 'parallel_http_analysis.png')
    plt.savefig(filepath, bbox_inches='tight', dpi=200)
    print(f"Graphs successfully saved as '{filepath}'.")
    plt.show()

def main():
    parser = argparse.ArgumentParser(description="Analyze HTTP Request-Response times from PCAP chunks in parallel.")
    parser.add_argument("-i", "--input_dir", required=True, help="Directory containing the split .pcap files")
    parser.add_argument("-o", "--output_dir", required=True, help="Directory to save the CSV and graph outputs")
    
    args = parser.parse_args()
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Create the search pattern based on the input directory
    pcap_pattern = os.path.join(args.input_dir, "*.pcap")
    pcap_files = glob.glob(pcap_pattern)
    
    if not pcap_files:
        print(f"Error: No PCAP files found matching '{pcap_pattern}'")
        return
        
    print(f"Found {len(pcap_files)} PCAP chunks in '{args.input_dir}'. Starting parallel processing...")
    
    all_times = []
    all_req_res_times = []
    
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [executor.submit(extract_http_time, pcap) for pcap in pcap_files]
        
        for future in concurrent.futures.as_completed(futures):
            chunk_times, chunk_req_res_times = future.result()
            all_times.extend(chunk_times)
            all_req_res_times.extend(chunk_req_res_times)
            
    if not all_req_res_times:
        print("No valid HTTP timings were extracted. Check your PCAP filters.")
        return
        
    print(f"\nTotal packets extracted across all chunks: {len(all_req_res_times)}")
    
    # Pass the output directory to the saving functions
    export_to_csv_gz(all_times, all_req_res_times, args.output_dir)
    plot_graphs(all_times, all_req_res_times, args.output_dir)

if __name__ == '__main__':
    main()