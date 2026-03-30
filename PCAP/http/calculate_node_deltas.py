#!/usr/bin/env python3
import pandas as pd
import numpy as np
import argparse
import csv
import os
import matplotlib.pyplot as plt

def load_delays(csv_path):
    """Loads latency data from standard CSV files."""
    df = pd.read_csv(csv_path)
    return df['HTTP_Response_Time_Seconds'].values

def calculate_delta_distribution(upstream_delays, downstream_delays, num_quantiles=10000):
    """
    Subtracts the downstream distribution from the upstream distribution 
    using Percentile Matching to find the isolated delay.
    (Increased to 10,000 quantiles for a high-resolution 1ms plot)
    """
    # Generate an array of percentiles (0.01%, 0.02% ... 100%)
    quantiles = np.linspace(0, 1, num_quantiles)
    
    # Get the exact latency values at those percentiles for both captures
    up_quantiles = np.quantile(upstream_delays, quantiles)
    down_quantiles = np.quantile(downstream_delays, quantiles)
    
    # Subtract downstream from upstream to isolate the node's processing time
    node_deltas = up_quantiles - down_quantiles
    
    # Floor to 100 microseconds (0.0001s) to account for statistical noise
    node_deltas = np.clip(node_deltas, a_min=0.0001, a_max=None)
    
    return node_deltas

def save_distribution(deltas, output_path):
    """Saves the calculated deltas to a standard CSV file."""
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['latency_seconds']) # Mininet proxy expects this name
        for val in deltas:
            writer.writerow([f"{val:.6f}"])
    print(f"Saved isolated node distribution to '{output_path}'")

def plot_isolated_distribution(deltas, csv_output_path):
    """Generates a probability distribution graph for the isolated node."""
    # Create the image filename based on the CSV filename
    base_name = os.path.splitext(csv_output_path)[0]
    image_path = f"{base_name}.png"
    node_name = os.path.basename(base_name).replace("_", " ").title()

    fig, ax1 = plt.subplots(figsize=(10, 6))
    fig.suptitle(f'Isolated Processing Delay: {node_name}', fontsize=16)

    # dynamically find the upper limit for the graph to zoom in on the relevant data
    max_plot_time = min(2.0, np.percentile(deltas, 99.5) * 1.5) 
    
    bins_1ms = np.arange(0, max_plot_time + 0.001, 0.001)
    
    counts, bin_edges = np.histogram(deltas, bins=bins_1ms)
    probabilities = counts / len(deltas)
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2

    # Plot the area and the curve
    ax1.fill_between(bin_centers, probabilities, color='mediumseagreen', alpha=0.5, label='Probability Area')
    ax1.plot(bin_centers, probabilities, color='darkgreen', linewidth=2, label='Empirical Curve')

    ax1.set_xlabel('Isolated Processing Time (Seconds)', fontsize=12)
    ax1.set_ylabel('Probability', fontsize=12)
    ax1.set_xlim(0, max_plot_time)
    
    ax1.grid(axis='y', alpha=0.3)
    ax1.grid(axis='x', alpha=0.1)
    ax1.legend(loc='upper right', fontsize=11)

    plt.tight_layout()
    plt.savefig(image_path, bbox_inches='tight', dpi=200)
    plt.close()
    
    print(f"Saved isolated node graph to '{image_path}'\n")

def main():
    parser = argparse.ArgumentParser(description="Calculate isolated component delays using Percentile Subtraction")
    parser.add_argument("--upstream", required=True, help="CSV of the ingress capture (e.g., adc_total.csv)")
    parser.add_argument("--downstream", required=True, help="CSV of the egress capture (e.g., waf_total.csv)")
    parser.add_argument("--out", required=True, help="Output filename for the isolated node CSV (e.g., adc_isolated.csv)")
    
    args = parser.parse_args()
    
    print(f"Loading Upstream: {args.upstream}")
    up_data = load_delays(args.upstream)
    
    print(f"Loading Downstream: {args.downstream}")
    down_data = load_delays(args.downstream)
    
    print("Calculating Statistical Delta...")
    isolated_delays = calculate_delta_distribution(up_data, down_data)
    
    save_distribution(isolated_delays, args.out)
    plot_isolated_distribution(isolated_delays, args.out)

if __name__ == '__main__':
    main()