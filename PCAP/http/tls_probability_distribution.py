#!/usr/bin/env python3
import dpkt
import socket
import argparse
import sys
import time
import os
import csv
import numpy as np
import matplotlib.pyplot as plt

# ==========================================
# GLOBAL CONFIGURATION
# ==========================================
BIN_SIZE_MS = 1.0           # Size of each histogram bucket (in milliseconds)
MAX_DISPLAY_TIME_MS = 2000  # Maximum time to display on the X-axis (in milliseconds)

def analyze_pcap(pcap_path, server_port):
    """Parses PCAP at high speed and extracts Relative Time and Delay."""
    print(f"[*] Starting high-speed parsing on {pcap_path}...")
    start_time = time.time()
    
    streams = {}
    delays_data = [] # Will store tuples of (Relative_Time, Delay)
    packet_count = 0
    first_ts = None

    try:
        with open(pcap_path, 'rb') as f:
            pcap = dpkt.pcap.Reader(f)
            linktype = pcap.datalink()
            
            for ts, buf in pcap:
                packet_count += 1
                
                # Capture the timestamp of the very first packet
                if first_ts is None:
                    first_ts = ts
                
                # --- HIGH SPEED LINK LAYER EXTRACTION ---
                try:
                    if linktype == dpkt.pcap.DLT_EN10MB:  # Standard Ethernet
                        eth = dpkt.ethernet.Ethernet(buf)
                        ip = eth.data
                    elif linktype == 113:  # LINUX_SLL
                        sll = dpkt.sll.SLL(buf)
                        ip = sll.data
                    elif linktype == 276:  # LINUX_SLL2 (Custom Bypass)
                        proto = int.from_bytes(buf[0:2], byteorder='big')
                        if proto == 0x0800:
                            ip = dpkt.ip.IP(buf[20:])
                        else:
                            continue
                    else:
                        if packet_count == 1:
                            print(f"[!] Warning: Unsupported Linktype {linktype}")
                        continue
                except Exception:
                    continue 

                # --- PROTOCOL FILTERING ---
                if not isinstance(ip, dpkt.ip.IP) or ip.p != dpkt.ip.IP_PROTO_TCP:
                    continue
                    
                tcp = ip.data
                if not isinstance(tcp, dpkt.tcp.TCP):
                    continue
                    
                payload = tcp.data
                
                # --- HEURISTIC: TLS Application Data (0x17) ---
                if len(payload) > 5 and payload[0] == 0x17:
                    src_port = tcp.sport
                    dst_port = tcp.dport
                    
                    if dst_port == server_port:
                        direction = 'C->S'
                        flow_id = (ip.src, src_port, ip.dst, dst_port)
                    elif src_port == server_port:
                        direction = 'S->C'
                        flow_id = (ip.dst, dst_port, ip.src, src_port)
                    else:
                        continue
                        
                    if flow_id not in streams:
                        streams[flow_id] = {'last_dir': None, 'last_client_time': None}
                        
                    flow = streams[flow_id]
                    
                    if direction == 'C->S':
                        flow['last_client_time'] = ts
                        flow['last_dir'] = 'C->S'
                        
                    elif direction == 'S->C':
                        if flow['last_dir'] == 'C->S' and flow['last_client_time'] is not None:
                            delay = ts - flow['last_client_time']
                            
                            # Filter out negative times or microsecond TCP window updates
                            if delay > 0.001: 
                                relative_time = flow['last_client_time'] - first_ts
                                delays_data.append((relative_time, delay))
                                
                        flow['last_dir'] = 'S->C'
                        
    except FileNotFoundError:
        print(f"[X] Error: Could not find file {pcap_path}")
        sys.exit(1)

    elapsed = time.time() - start_time
    print(f"[*] Parsed {packet_count} packets in {elapsed:.2f} seconds.")
    return delays_data

def export_to_csv(delays_data, output_dir, csv_name):
    """Writes the aggregated data to a standard CSV file."""
    if not delays_data:
        return
        
    # Ensure the name ends with .csv
    if not csv_name.endswith('.csv'):
        csv_name += '.csv'
        
    filename = os.path.join(output_dir, csv_name)
    print(f"\n[*] Exporting {len(delays_data)} records to {filename}...")
    
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Relative_Time_Seconds', 'HTTP_Response_Time_Seconds'])
        writer.writerows(delays_data)
        
    print(f"[+] Export complete. Data saved to '{filename}'.")

def plot_distribution(delays_data, output_dir, graph_name):
    """Generates a Probability Distribution graph and saves it."""
    if not delays_data:
        print("[!] No valid TLS request/response pairs found to plot.")
        return

    print(f"\n[*] Generating Probability Distribution graph...")
    
    # Extract just the delays (index 1) and convert to ms
    only_delays = [d[1] for d in delays_data]
    delays_ms = np.array(only_delays) * 1000  
    
    strict_bins = np.arange(0, MAX_DISPLAY_TIME_MS + BIN_SIZE_MS, BIN_SIZE_MS)
    
    plt.figure(figsize=(12, 6))
    plt.hist(delays_ms, bins=strict_bins, density=True, alpha=0.75, color='#2ecc71', edgecolor='black')
    plt.xlim(0, MAX_DISPLAY_TIME_MS)
    
    mean_delay = np.mean(delays_ms)
    p95_delay = np.percentile(delays_ms, 95)
    
    plt.axvline(mean_delay, color='red', linestyle='dashed', linewidth=2, label=f'Mean: {mean_delay:.2f}ms')
    plt.axvline(p95_delay, color='#e67e22', linestyle='dashed', linewidth=2, label=f'95th Pctl: {p95_delay:.2f}ms')
    
    plt.title(f'Encrypted HTTP Response Time: Probability Distribution\n(Bin Size: {BIN_SIZE_MS}ms)', fontsize=14, fontweight='bold')
    plt.xlabel('Response Delay (Milliseconds)', fontsize=12)
    plt.ylabel('Probability Density (Frequency)', fontsize=12)
    plt.legend(loc='upper right', fontsize=11)
    
    # Add grid lines for readability
    plt.grid(axis='y', alpha=0.3)
    plt.grid(axis='x', alpha=0.1)
    plt.tight_layout()
    
    # Save the graph
    if not graph_name.endswith('.png'):
        graph_name += '.png'
        
    filepath = os.path.join(output_dir, graph_name)
    plt.savefig(filepath, bbox_inches='tight', dpi=200)
    print(f"[+] Graph successfully saved as '{filepath}'.")
    
    # Display the plot window
    plt.show()

def main():
    parser = argparse.ArgumentParser(description="High-Speed TLS Delay Analyzer & Exporter.")
    parser.add_argument("-i", "--input_file", required=True, help="Path to the input .pcap file")
    parser.add_argument("-o", "--output_dir", required=True, help="Directory to save the CSV and graph outputs")
    parser.add_argument("-p", "--port", type=int, default=443, help="Server port to monitor (default: 443)")
    parser.add_argument("--csv_name", default="tls_delays.csv", help="Name of the output CSV file")
    parser.add_argument("--graph_name", default="probability_distribution.png", help="Name of the output Graph file")
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.isfile(args.input_file):
        print(f"[X] Error: Input file '{args.input_file}' does not exist.")
        return
        
    # Automatically create the output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Run pipeline
    extracted_data = analyze_pcap(args.input_file, args.port)
    
    if not extracted_data:
        print("[!] No valid TLS timings were extracted. Check your PCAP or Server Port.")
        return
        
    print(f"\n[*] Total valid TLS transactions extracted: {len(extracted_data)}")
    
    export_to_csv(extracted_data, args.output_dir, args.csv_name)
    plot_distribution(extracted_data, args.output_dir, args.graph_name)

if __name__ == "__main__":
    main()