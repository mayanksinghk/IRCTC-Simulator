#!/usr/bin/env python3
import csv
import matplotlib.pyplot as plt
import numpy as np

# -------------------------------------------------------------
# LOAD RTT FROM CSV
# -------------------------------------------------------------
def load_rtt(input_csv):
    all_rtt = []
    get_rtt = []
    post_rtt = []

    with open(input_csv, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                m = row["method"].strip().upper()
                rtt = float(row["rtt"])
            except:
                continue

            all_rtt.append(rtt)

            if m == "GET":
                get_rtt.append(rtt)

            elif m == "POST":
                post_rtt.append(rtt)

    return all_rtt, get_rtt, post_rtt


# -------------------------------------------------------------
# SAVE RTT CSV
# -------------------------------------------------------------
def save_rtt_csv(rtt_list, output_csv):
    with open(output_csv, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["rtt_seconds"])
        for rtt in rtt_list:
            w.writerow([f"{rtt:.6f}"])
    print(f"[+] Saved: {output_csv}")


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


# -------------------------------------------------------------
# RTT vs Packet Counter
# -------------------------------------------------------------
def plot_rtt_vs_counter(rtt_list, png_file, title, max_rtt_ms=10000):
    rtt_ms = [r * 1000 for r in rtt_list if r * 1000 <= max_rtt_ms]

    if not rtt_ms:
        print(f"[!] No RTT values to plot for {png_file}")
        return

    counters = list(range(1, len(rtt_ms) + 1))

    plt.figure(figsize=(12, 5))
    plt.plot(counters, rtt_ms, linestyle="", marker=".", markersize=3, alpha=0.6)
    plt.title(title)
    plt.xlabel("Packet Index")
    plt.ylabel("RTT (ms)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(png_file, dpi=300)
    print(f"[+] Saved graph: {png_file}")


# -------------------------------------------------------------
# MAIN
# -------------------------------------------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RTT Graph Generator for HTTP CSV")
    parser.add_argument("-i", "--input", required=True, help="Input HTTP RTT CSV")
    parser.add_argument("--bin", type=int, default=1, help="Histogram bin size in ms")
    parser.add_argument("--max", type=int, default=10000, help="Max RTT in ms")
    args = parser.parse_args()

    # Load RTT sets
    all_rtt, get_rtt, post_rtt = load_rtt(args.input)

    # Save separate CSVs
    save_rtt_csv(all_rtt, "all_rtt.csv")
    save_rtt_csv(get_rtt, "get_rtt.csv")
    save_rtt_csv(post_rtt, "post_rtt.csv")

    # Graphs for ALL
    plot_rtt_distribution(
        all_rtt, "all_rtt_dist.png",
        "RTT Distribution (ALL Methods)",
        bin_size_ms=args.bin,
        max_rtt_ms=args.max
    )

    plot_rtt_vs_counter(
        all_rtt, "all_rtt_counter.png",
        "RTT vs Packet Index (ALL Methods)",
        max_rtt_ms=args.max
    )

    # Graphs for GET
    plot_rtt_distribution(
        get_rtt, "get_rtt_dist.png",
        "RTT Distribution (GET Only)",
        bin_size_ms=args.bin,
        max_rtt_ms=args.max
    )

    plot_rtt_vs_counter(
        get_rtt, "get_rtt_counter.png",
        "RTT vs Packet Index (GET Only)",
        max_rtt_ms=args.max
    )

    # Graphs for POST
    plot_rtt_distribution(
        post_rtt, "post_rtt_dist.png",
        "RTT Distribution (POST Only)",
        bin_size_ms=args.bin,
        max_rtt_ms=args.max
    )

    plot_rtt_vs_counter(
        post_rtt, "post_rtt_counter.png",
        "RTT vs Packet Index (POST Only)",
        max_rtt_ms=args.max
    )

    print("\n[+] ALL processing done.")
