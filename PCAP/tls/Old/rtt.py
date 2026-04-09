#!/usr/bin/env python3
import csv
import ipaddress
import matplotlib.pyplot as plt
import numpy as np

# -------------------------
# Server subnets
# -------------------------
SERVER_SUBNETS = [
    "203.176.112.0/24",
    "203.176.113.0/24",
    "103.252.143.0/24",
    "103.252.142.0/24",
    "103.110.246.0/24",
]
SERVER_NETS = [ipaddress.ip_network(s) for s in SERVER_SUBNETS]

def ip_in_subnets(ip_str):
    ip = ipaddress.ip_address(ip_str)
    return any(ip in net for net in SERVER_NETS)

# -------------------------
# Compute RTTs
# -------------------------
def compute_rtt(input_csv: str, min_tls_len=600):
    """
    Reads TLS CSV and computes RTTs per flow.
    Returns server_to_client times and RTTs in seconds.
    """
    last_client_packet = {}  # key: (client_ip, client_port, server_ip, server_port)
    rtt_list = []
    time_list = []

    with open(input_csv, "r") as f_in:
        reader = csv.DictReader(f_in)

        for row in reader:
            t = float(row["time"])
            src = row["src"]
            sport = int(row["src_port"])
            dst = row["dst"]
            dport = int(row["dst_port"])
            tls_len = int(row.get("length", 0))

            # Ignore small TLS records
            if tls_len < min_tls_len:
                continue

            # Server -> Client packet
            if ip_in_subnets(src):
                client_key = (dst, dport, src, sport)
                if client_key in last_client_packet:
                    rtt = t - last_client_packet[client_key]
                    rtt_list.append(rtt)
                    time_list.append(t)
            # Client -> Server packet
            elif ip_in_subnets(dst):
                client_key = (src, sport, dst, dport)
                last_client_packet[client_key] = t

    return time_list, rtt_list

# -------------------------
# Save RTT CSV
# -------------------------
def save_rtt_csv(time_list, rtt_list, output_csv):
    with open(output_csv, "w", newline="") as f_out:
        writer = csv.writer(f_out)
        writer.writerow(["server_to_client_time", "rtt_seconds"])
        for t, rtt in zip(time_list, rtt_list):
            writer.writerow([f"{t:.6f}", f"{rtt:.6f}"])
    print(f"[+] RTT CSV saved: {output_csv}")

# -------------------------
# RTT distribution histogram with summary
# -------------------------
def plot_rtt_distribution(rtt_list, png_file="rtt_distribution.png", bin_size_ms=1, max_rtt_ms=10000):
    """
    Plots histogram of RTTs in milliseconds.
    bin_size_ms: size of each RTT bin in ms
    max_rtt_ms: maximum RTT to plot in ms (filter outliers)
    Also prints a summary of RTT statistics.
    """
    rtt_ms = [rtt*1000 for rtt in rtt_list if rtt*1000 <= max_rtt_ms]

    # Summary
    total_packets = len(rtt_list)
    filtered_packets = len(rtt_ms)
    min_rtt = np.min(rtt_ms) if rtt_ms else 0
    max_rtt = np.max(rtt_ms) if rtt_ms else 0
    avg_rtt = np.mean(rtt_ms) if rtt_ms else 0
    median_rtt = np.median(rtt_ms) if rtt_ms else 0

    print("\n[+] RTT Distribution Summary:")
    print(f"    Total packets processed: {total_packets}")
    print(f"    RTTs within {max_rtt_ms} ms: {filtered_packets}")
    print(f"    Min RTT: {min_rtt:.3f} ms")
    print(f"    Max RTT: {max_rtt:.3f} ms")
    print(f"    Average RTT: {avg_rtt:.3f} ms")
    print(f"    Median RTT: {median_rtt:.3f} ms\n")

    bins = list(range(0, int(max_rtt_ms)+bin_size_ms, bin_size_ms))

    plt.figure(figsize=(12,6))
    plt.hist(rtt_ms, bins=bins, edgecolor='black')
    plt.title("TLS RTT Distribution")
    plt.xlabel("RTT (ms)")
    plt.ylabel("Number of Packets")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(png_file, dpi=300)
    print(f"[+] RTT distribution histogram saved: {png_file}")
    # plt.show()
# -------------------------
# RTT vs packet counter
# -------------------------
def plot_rtt_vs_counter(rtt_list, png_file="rtt_vs_counter.png", max_rtt_ms=10000):
    """
    Plots RTT vs packet counter, filtering out very high RTTs.
    """
    rtt_ms = [rtt*1000 for rtt in rtt_list]
    filtered_rtt = [r for r in rtt_ms if r <= max_rtt_ms]
    counters = list(range(1, len(filtered_rtt)+1))

    plt.figure(figsize=(12,6))
    plt.plot(counters, filtered_rtt, marker='o', linestyle='', markersize=3, alpha=0.6)
    plt.title(f"TLS RTT vs Packet Counter (max RTT={max_rtt_ms} ms)")
    plt.xlabel("Packet Counter")
    plt.ylabel("RTT (ms)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(png_file, dpi=300)
    print(f"[+] RTT vs counter plot saved: {png_file}")
    # plt.show()

# -------------------------
# Main
# -------------------------
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Compute TLS RTT and plot graphs")
    parser.add_argument("-i", "--input", required=True, help="Input TLS CSV file")
    parser.add_argument("-o", "--output", required=True, help="Output RTT CSV file")
    parser.add_argument("--png_dist", default="rtt_distribution.png", help="Output histogram PNG")
    parser.add_argument("--png_counter", default="rtt_vs_counter.png", help="Output RTT vs counter PNG")
    parser.add_argument("--min_tls_len", type=int, default=600, help="Ignore TLS records smaller than this")
    parser.add_argument("--bin_size", type=int, default=1, help="Histogram bin size in ms")
    parser.add_argument("--max_rtt", type=int, default=10000, help="Max RTT to plot (ms) to remove outliers")
    args = parser.parse_args()

    # Compute RTT
    time_list, rtt_list = compute_rtt(args.input, min_tls_len=args.min_tls_len)

    # Save RTT CSV
    save_rtt_csv(time_list, rtt_list, args.output)

    # Plot histogram
    plot_rtt_distribution(rtt_list, png_file=args.png_dist, bin_size_ms=args.bin_size, max_rtt_ms=args.max_rtt)

    # Plot RTT vs counter
    plot_rtt_vs_counter(rtt_list, png_file=args.png_counter, max_rtt_ms=args.max_rtt)
