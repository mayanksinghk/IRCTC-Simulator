#!/usr/bin/env python3
import argparse
import numpy as np
import matplotlib.pyplot as plt
import sys
import os

def visualize_netem_dist(dist_file, mean_ms, jitter_ms):
    print(f"Loading '{dist_file}'...")
    
    if not os.path.exists(dist_file):
        print(f"Error: File '{dist_file}' not found.")
        sys.exit(1)

    # 1. Read the raw table values safely
    table_values_list = []
    try:
        with open(dist_file, 'r') as f:
            for line in f:
                line = line.strip()
                # Skip completely empty lines and comment lines
                if not line or line.startswith('#'):
                    continue
                
                # Split the line into individual numbers
                for token in line.split():
                    try:
                        table_values_list.append(float(token))
                    except ValueError:
                        # If a weird non-numeric string sneaks in, just skip it
                        continue
                        
        table_values = np.array(table_values_list)
        
        if len(table_values) == 0:
            print("Error: Could not find any valid numbers in the file.")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error parsing file: {e}")
        sys.exit(1)

    print(f"Successfully loaded {len(table_values)} data points.")

    # 2. Normalize the distribution table
    max_val = np.max(np.abs(table_values))
    if max_val > 2.0:
        print("Detected 16-bit integer format. Normalizing to [-1.0, 1.0]...")
        table_values = table_values / 32768.0
    else:
        print("Detected float format. Using values directly...")

    # 3. Apply the NetEm Formula
    simulated_latencies = mean_ms + (table_values * jitter_ms)

    # 4. Check for the Negative Latency Bug
    negative_count = np.sum(simulated_latencies < 0)
    if negative_count > 0:
        print("\n" + "!"*60)
        print(f"WARNING: {negative_count} points ({negative_count/len(table_values)*100:.2f}%) evaluated to a negative latency!")
        print("NetEm cannot delay packets backwards in time. Depending on the kernel,")
        print("these will either be clamped to 0ms (creating a massive spike) or dropped.")
        print("!"*60 + "\n")

    # 5. Plot the result
    plt.figure(figsize=(12, 6))
    
    plt.hist(simulated_latencies, bins=200, density=True, color='#e74c3c', alpha=0.7, edgecolor='black', linewidth=0.5)
    
    plt.title(f"Simulated tc netem Distribution\n(Mean: {mean_ms}ms | Jitter: {jitter_ms}ms)", fontsize=14)
    plt.xlabel("Latency (Milliseconds)", fontsize=12)
    plt.ylabel("Probability Density", fontsize=12)
    plt.grid(True, linestyle='--', alpha=0.5)
    
    plt.axvline(x=0, color='black', linestyle='--', linewidth=2, label="0ms Boundary (Physical Limit)")
    plt.legend()
    
    plt.tight_layout()
    
    output_img = f"simulated_{os.path.basename(dist_file)}.png"
    plt.savefig(output_img, dpi=300)
    print(f"Plot saved to '{output_img}'.")
    plt.show()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Visualize a Linux tc netem .dist file.")
    parser.add_argument("dist_file", help="Path to your .dist file")
    parser.add_argument("mean", type=float, help="The base delay (mean) in ms used in your tc command")
    parser.add_argument("jitter", type=float, help="The jitter (std dev) in ms used in your tc command")
    
    args = parser.parse_args()
    
    visualize_netem_dist(args.dist_file, args.mean, args.jitter)