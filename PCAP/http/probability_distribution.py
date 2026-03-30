#!/usr/bin/env python3
import subprocess
import matplotlib.pyplot as plt
import numpy as np
import os
import csv
import argparse

# --- CONFIGURATION ---
MAX_TIME_SECONDS = 2.0

def extract_http_time(pcap_file):
    """
    Extracts frame.time_relative and http.time from a single PCAP file using tshark.
    """
    print(f"[{os.path.basename(pcap_file)}] Started processing...")
    
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

def export_to_csv(times, req_res_times, output_dir, csv_name):
    """Writes the aggregated data to a standard CSV file."""
    # Ensure the name ends with .csv
    if not csv_name.endswith('.csv'):
        csv_name += '.csv'
        
    filename = os.path.join(output_dir, csv_name)
    print(f"\nExporting {len(times)} records to {filename}...")
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Relative_Time_Seconds', 'HTTP_Response_Time_Seconds'])
        writer.writerows(zip(times, req_res_times))
        
    print(f"Export complete. Data saved to '{filename}'.")

def plot_graphs(times, req_res_times, output_dir, graph_name):
    """Generates a single Probability Distribution graph and saves it to the output directory."""
    print("\nGenerating Probability Distribution graph...")
    
    fig, ax1 = plt.subplots(figsize=(12, 6))
    fig.suptitle(f'HTTP Response Time: Probability Distribution (< {MAX_TIME_SECONDS}s)', fontsize=16)
    
    # Define the 1ms bins (0.001 seconds)
    bins_1ms = np.arange(0, MAX_TIME_SECONDS + 0.001, 0.001)
    
    # 1. Calculate the Raw Frequencies (Counts per bucket)
    counts, bin_edges = np.histogram(req_res_times, bins=bins_1ms)
    
    # 2. Calculate the "Real" Probability (Frequency / Total Population)
    total_population = len(req_res_times)
    probabilities = counts / total_population
    
    # Find the center point of each 1ms bin for accurate plotting
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    # Plot the Empirical Probability Curve as a Line
    ax1.plot(bin_centers, probabilities, color='crimson', linewidth=2, label='Empirical Probability Curve (Continuous)')
    
    # Formatting the axes
    ax1.set_xlabel('Time between Request and Response (Seconds)', fontsize=12)
    ax1.set_ylabel('Probability (Sum of all bins = 1.0)', fontsize=12)
    ax1.set_xlim(0, MAX_TIME_SECONDS)
    
    # Add grid lines for readability
    ax1.grid(axis='y', alpha=0.3)
    ax1.grid(axis='x', alpha=0.1)
    ax1.legend(loc='upper right', fontsize=11)
    
    # Adjust layout and save
    plt.tight_layout()
    
    # Ensure the name ends with .png
    if not graph_name.endswith('.png'):
        graph_name += '.png'
        
    filepath = os.path.join(output_dir, graph_name)
    plt.savefig(filepath, bbox_inches='tight', dpi=200)
    print(f"Graph successfully saved as '{filepath}'.")
    
    # Display the plot window
    plt.show()

def main():
    parser = argparse.ArgumentParser(description="Extract and Plot HTTP Probability Distribution.")
    parser.add_argument("-i", "--input_file", required=True, help="Path to the input .pcap file")
    parser.add_argument("-o", "--output_dir", required=True, help="Directory to save the CSV and graph outputs")
    parser.add_argument("--csv_name", default="http_request_response_times.csv", help="Name of the output CSV file")
    parser.add_argument("--graph_name", default="probability_distribution.png", help="Name of the output Graph file")
    
    args = parser.parse_args()
    
    if not os.path.isfile(args.input_file):
        print(f"Error: Input file '{args.input_file}' does not exist.")
        return
        
    os.makedirs(args.output_dir, exist_ok=True)
    
    print(f"Starting processing for file: '{args.input_file}'")
    
    # Serial execution instead of parallel
    all_times, all_req_res_times = extract_http_time(args.input_file)
            
    if not all_req_res_times:
        print("No valid HTTP timings were extracted. Check your PCAP filters.")
        return
        
    print(f"\nTotal packets extracted: {len(all_req_res_times)}")
    
    export_to_csv(all_times, all_req_res_times, args.output_dir, args.csv_name)
    plot_graphs(all_times, all_req_res_times, args.output_dir, args.graph_name)

if __name__ == '__main__':
    main()