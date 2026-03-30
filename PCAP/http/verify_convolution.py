#!/usr/bin/env python3
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import argparse
import os

def load_delays(csv_path):
    """Loads latency data from the CSV."""
    df = pd.read_csv(csv_path)
    # Check for both possible column names based on your previous outputs
    if 'HTTP_Response_Time_Seconds' in df.columns:
        return df['HTTP_Response_Time_Seconds'].values
    elif 'latency_seconds' in df.columns:
        return df['latency_seconds'].values
    else:
        raise KeyError(f"Could not find latency column in {csv_path}")

def verify_convolution(isolated_csv, downstream_csv, original_upstream_csv, output_dir):
    print(f"Loading data...")
    isolated_delays = load_delays(isolated_csv)
    downstream_delays = load_delays(downstream_csv)
    original_delays = load_delays(original_upstream_csv)

    print("Simulating Mininet Behavior (Monte Carlo Convolution)...")
    # Simulate 1,000,000 packets passing through Mininet
    num_simulations = 1000000
    
    # Randomly sample from the isolated node (just like proxy #1)
    simulated_isolated = np.random.choice(isolated_delays, size=num_simulations, replace=True)
    
    # Randomly sample from the downstream network (just like proxy #2)
    simulated_downstream = np.random.choice(downstream_delays, size=num_simulations, replace=True)
    
    # Add them together! This is the convolution.
    simulated_total = simulated_isolated + simulated_downstream

    print("Generating verification graph...")
    fig, ax = plt.subplots(figsize=(12, 6))
    fig.suptitle('Verification: Emulated Network vs Real PCAP', fontsize=16)

    # Determine max X axis for clean plotting
    max_time = min(2.0, np.percentile(original_delays, 99) * 1.5)
    bins_1ms = np.arange(0, max_time + 0.001, 0.001)

    # Plot 1: The Original Ground Truth (From PCAP)
    counts_orig, bin_edges = np.histogram(original_delays, bins=bins_1ms)
    prob_orig = counts_orig / len(original_delays)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    # Plot 2: The Simulated Mininet Result (Convolution)
    counts_sim, _ = np.histogram(simulated_total, bins=bins_1ms)
    prob_sim = counts_sim / len(simulated_total)

    # Draw the plots
    ax.fill_between(bin_centers, prob_orig, color='skyblue', alpha=0.5, label='Original PCAP (Ground Truth)')
    ax.plot(bin_centers, prob_sim, color='crimson', linewidth=2, linestyle='--', label='Mininet Emulation (Convolved)')

    # Formatting
    ax.set_xlabel('Cumulative Response Time (Seconds)', fontsize=12)
    ax.set_ylabel('Probability', fontsize=12)
    ax.set_xlim(0, max_time)
    ax.grid(axis='y', alpha=0.3)
    ax.grid(axis='x', alpha=0.1)
    ax.legend(loc='upper right', fontsize=12)

    # Save output
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "convolution_verification.png")
    plt.tight_layout()
    plt.savefig(output_path, bbox_inches='tight', dpi=200)
    print(f"Verification graph saved to: {output_path}")
    plt.show()

def main():
    parser = argparse.ArgumentParser(description="Verify Mininet isolated node delays via Monte Carlo Convolution.")
    parser.add_argument("--isolated", required=True, help="Isolated node CSV (e.g., adc_isolated.csv)")
    parser.add_argument("--downstream", required=True, help="Downstream network CSV (e.g., waf_total.csv)")
    parser.add_argument("--original", required=True, help="Original upstream CSV to verify against (e.g., adc_total.csv)")
    parser.add_argument("--outdir", default="./Verification", help="Directory to save the verification plot")
    
    args = parser.parse_args()
    
    verify_convolution(args.isolated, args.downstream, args.original, args.outdir)

if __name__ == '__main__':
    main()