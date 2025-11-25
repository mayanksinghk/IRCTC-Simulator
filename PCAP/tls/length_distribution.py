#!/usr/bin/env python3
import csv
import matplotlib.pyplot as plt
import os
import numpy as np

# -------------------------
# Configuration
# -------------------------
input_csv = "./6-7/6-7_tls_rtt.csv"  # replace with your CSV file path
output_png = os.path.splitext(input_csv)[0] + "_length_distribution.png"

# -------------------------
# Read lengths
# -------------------------
lengths = []

with open(input_csv, "r") as f:
    reader = csv.DictReader(f)
    for row in reader:
        try:
            l = int(row["length"])
            lengths.append(l)
        except ValueError:
            continue

if not lengths:
    print("[!] No valid lengths found in the CSV.")
    exit(1)

# -------------------------
# Auto bin size and max length
# -------------------------
max_len = max(lengths)
bin_count = 50  # default number of bins
bin_size = max(1, max_len // bin_count)

# -------------------------
# Print statistics
# -------------------------
print(f"Packet Length Statistics:")
print(f"  Count: {len(lengths)}")
print(f"  Min: {min(lengths)}")
print(f"  Max: {max_len}")
print(f"  Average: {np.mean(lengths):.2f}")
print(f"  Median: {np.median(lengths)}")

# -------------------------
# Plot histogram
# -------------------------
plt.figure(figsize=(10, 5))
bins = range(0, max_len + bin_size, bin_size)
plt.hist(lengths, bins=bins, edgecolor="black")
plt.title("Packet Length Distribution")
plt.xlabel("Length (bytes)")
plt.ylabel("Count")
plt.grid(True)
plt.tight_layout()
plt.savefig(output_png, dpi=300)
print(f"[+] Packet length distribution saved to: {output_png}")

