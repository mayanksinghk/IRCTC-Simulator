#!/usr/bin/env python3
import csv
import matplotlib.pyplot as plt
import os
import numpy as np

# -------------------------
# Input CSV
# -------------------------
input_csv = "./10/10_http_rtt.csv"
base_name = os.path.splitext(os.path.basename(input_csv))[0]

# -------------------------
# Master list for combined sizes
# -------------------------
master_sizes = []

with open(input_csv, "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            req_len = int(row["request_size"])
            resp_len = int(row["response_size"])
            master_sizes.extend([req_len, resp_len])  # combine
        except ValueError:
            continue

if not master_sizes:
    print("[!] No valid sizes found in CSV.")
    exit(1)

# -------------------------
# Dynamic bin size
# -------------------------
max_size = max(master_sizes)
bin_count = 50
bin_size = max(1, max_size // bin_count)
bins = np.arange(0, max_size + bin_size, bin_size)

# -------------------------
# Plot distribution
# -------------------------
plt.figure(figsize=(12, 6))
plt.hist(master_sizes, bins=bins, color='skyblue', edgecolor='black')
plt.title("Combined Request & Response Packet Size Distribution")
plt.xlabel("Packet Size (bytes)")
plt.ylabel("Count")
plt.grid(axis='y', alpha=0.75)
plt.tight_layout()

# -------------------------
# Save plot
# -------------------------
output_png = f"{base_name}_combined_size_distribution.png"
plt.savefig(output_png, dpi=300)
plt.close()
print(f"[+] Combined packet size distribution saved: {output_png}")
