#!/usr/bin/env python3
"""
Compute HTTP RTT and produce plots. This script reads an input CSV file containing HTTP RTT data, processes it to extract RTT values for all requests, GET requests, and POST requests, and generates plots to visualize the RTT distributions and their relation to packet counters.
"""

import csv
import os
import matplotlib.pyplot as plt
import numpy as np

# -------------------------
# Compute RTTs
# -------------------------
def compute_rtt(input_csv: str):
    """
    Reads HTTP RTT CSV and extracts:
    - all RTT
    - GET RTT
    - POST RTT
    """
    all_times, all_rtts = [], []
    get_times, get_rtts = [], []
    post_times, post_rtts = [], []

    with open(input_csv, "r") as f_in:
        reader = csv.DictReader(f_in)

        for row in reader:
            # Correct field names
            t = float(row["response_time_rel"])
            rtt = float(row["rtt"])
            method = row["method"].upper()

            # ALL
            all_times.append(t)
            all_rtts.append(rtt)

            # GET only
            if method == "GET":
                get_times.append(t)
                get_rtts.append(rtt)

            # POST only
            elif method == "POST":
                post_times.append(t)
                post_rtts.append(rtt)

    return (all_times, all_rtts), (get_times, get_rtts), (post_times, post_rtts)



# -------------------------
# Save RTT CSV
# -------------------------
def save_rtt_csv(time_list, rtt_list, output_csv):
    with open(output_csv, "w", newline="") as f_out:
        writer = csv.writer(f_out)
        writer.writerow(["response_time", "rtt_seconds"])
        for t, rtt in zip(time_list, rtt_list):
            writer.writerow([f"{t:.6f}", f"{rtt:.6f}"])
    print(f"[+] RTT CSV saved: {output_csv}")


# -------------------------------------------------------------
# Plot RTT Distribution
# -------------------------------------------------------------
def plot_rtt_distribution(rtt_list, png_file, title, bin_size_ms=1, max_rtt_ms=10000):
    rtt_ms = [r * 1000 for r in rtt_list if r * 1000 <= max_rtt_ms]

    if not rtt_ms:
        print(f"[!] No RTT values to plot for {png_file}")
        return

    min_rtt = np.min(rtt_ms)
    max_rtt = np.max(rtt_ms)
    avg_rtt = np.mean(rtt_ms)
    median_rtt = np.median(rtt_ms)

    print(f"\n=== {title} ===")
    print(f"Count: {len(rtt_ms)}")
    print(f"Min: {min_rtt:.3f} ms")
    print(f"Max: {max_rtt:.3f} ms")
    print(f"Avg: {avg_rtt:.3f} ms")
    print(f"Median: {median_rtt:.3f} ms")

    bins = np.arange(0, max_rtt_ms + bin_size_ms, bin_size_ms)

    plt.figure(figsize=(12, 5))
    plt.hist(rtt_ms, bins=bins, edgecolor="black")
    plt.title(title)
    plt.xlabel("RTT (ms)")
    plt.ylabel("Count")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(png_file, dpi=300)
    print(f"[+] Saved graph: {png_file}")



# -------------------------
# Build PNG names
# -------------------------
import os

def build_png_name(output_folder, base_name, suffix, max_rtt):
    return os.path.join(output_folder, f"{base_name}_{suffix}_{max_rtt}.png")



# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compute HTTP RTT and produce plots")
    parser.add_argument("-i", "--input", required=True, help="Input RTT CSV file")
    parser.add_argument("--bin_size", type=int, default=1, help="Histogram bin size (ms)")
    parser.add_argument("--max_rtt", type=int, default=1000, help="Max RTT for plots")
    parser.add_argument("-o", "--output", required=True, help="Output directory")
    args = parser.parse_args()

    # Load RTT sets
    (all_t, all_rtt), (get_t, get_rtt), (post_t, post_rtt) = compute_rtt(args.input)
    base = os.path.splitext(os.path.basename(args.input))[0]

    # -------------------------
    # Generate PNG names
    # -------------------------
    all_dist_png = build_png_name(args.output, base, "all_rtt_distribution", args.max_rtt)
    all_counter_png = build_png_name(args.output, base, "all_rtt_counter", args.max_rtt)

    get_dist_png = build_png_name(args.output, base, "get_rtt_distribution", args.max_rtt)
    get_counter_png = build_png_name(args.output, base, "get_rtt_counter", args.max_rtt)

    post_dist_png = build_png_name(args.output, base, "post_rtt_distribution", args.max_rtt)
    post_counter_png = build_png_name(args.output, base, "post_rtt_counter", args.max_rtt)

    # -------------------------
    # Plot
    # -------------------------
    plot_rtt_distribution(
        all_rtt, all_dist_png,
        title="All RTT Distribution",
        bin_size_ms=args.bin_size,
        max_rtt_ms=args.max_rtt
    )

    plot_rtt_distribution(
        get_rtt, get_dist_png,
        title="GET RTT Distribution",
        bin_size_ms=args.bin_size,
        max_rtt_ms=args.max_rtt
    )

    plot_rtt_distribution(
        post_rtt, post_dist_png,
        title="POST RTT Distribution",
        bin_size_ms=args.bin_size,
        max_rtt_ms=args.max_rtt
    )


    print("\n[✓] All graphs generated successfully.\n")
