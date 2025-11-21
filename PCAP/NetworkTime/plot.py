#!/usr/bin/env python3
import argparse
import numpy as np
import plotly.graph_objects as go
from scipy.stats import gaussian_kde
import json

# -------------------------
# Argument parser
# -------------------------
parser = argparse.ArgumentParser(description="Interactive RTT distribution plot + detailed stats")
parser.add_argument("-f", "--file", required=True, help="Input RTT file (seconds per line)")
parser.add_argument("--unit", choices=["us", "ms"], default="us", help="Output unit")
parser.add_argument("--html", default="rtt_distribution.html", help="Save interactive HTML plot")
parser.add_argument("--stats", default="rtt_stats.json", help="Save detailed stats report (JSON)")
args = parser.parse_args()

rtt_file = args.file
unit = args.unit

# -------------------------
# Load RTT data
# -------------------------
with open(rtt_file, "r") as f:
    rtt_values = [float(line.strip()) for line in f if line.strip()]

rtt_array = np.array(rtt_values)
if len(rtt_array) == 0:
    raise ValueError("No RTT values found in the file!")

# -------------------------
# Scale to µs or ms
# -------------------------
if unit == "us":
    rtt_array = rtt_array * 1_000_000  # seconds → µs
elif unit == "ms":
    rtt_array = rtt_array * 1000       # seconds → ms

unit_label = "µs" if unit=="us" else "ms"

# -------------------------
# Compute histogram
# -------------------------
hist_counts, hist_bins = np.histogram(rtt_array, bins=100)

# -------------------------
# Compute KDE
# -------------------------
kde = gaussian_kde(rtt_array)
x_kde = np.linspace(min(rtt_array), max(rtt_array), 1000)
y_kde = kde(x_kde) * len(rtt_array) * (hist_bins[1]-hist_bins[0])  # scale to histogram counts

# -------------------------
# Compute detailed statistics
# -------------------------
mean_rtt = np.mean(rtt_array)
median_rtt = np.median(rtt_array)
mode_rtt = hist_bins[np.argmax(hist_counts)]
std_rtt = np.std(rtt_array)
min_rtt = np.min(rtt_array)
max_rtt = np.max(rtt_array)
percentiles = np.percentile(rtt_array, [1,5,10,25,50,75,90,95,99,99.9])
count = len(rtt_array)

stats = {
    "count": count,
    "unit": unit_label,
    "mean": mean_rtt,
    "median": median_rtt,
    "mode_approx": mode_rtt,
    "std_dev": std_rtt,
    "min": min_rtt,
    "max": max_rtt,
    "percentiles": {
        "1": percentiles[0],
        "5": percentiles[1],
        "10": percentiles[2],
        "25": percentiles[3],
        "50": percentiles[4],
        "75": percentiles[5],
        "90": percentiles[6],
        "95": percentiles[7],
        "99": percentiles[8],
        "99.9": percentiles[9]
    }
}

# Print stats
print("\n=== Detailed RTT Statistics ===")
for k,v in stats.items():
    if k != "percentiles":
        print(f"{k}: {v}")
print("Percentiles:")
for k,v in stats["percentiles"].items():
    print(f"  {k}th percentile: {v}")

# Save stats as JSON
with open(args.stats, "w") as jf:
    json.dump(stats, jf, indent=4)
print(f"\nDetailed statistics saved to: {args.stats}")

# -------------------------
# Create interactive plot (Plotly)
# -------------------------
fig = go.Figure()

# Histogram
fig.add_trace(go.Histogram(
    x=rtt_array,
    nbinsx=100,
    name='Histogram',
    marker_color='skyblue',
    opacity=0.7
))

# KDE line
fig.add_trace(go.Scatter(
    x=x_kde,
    y=y_kde,
    mode='lines',
    line=dict(color='red', width=2),
    name='KDE'
))

# Mean line
fig.add_trace(go.Scatter(
    x=[mean_rtt, mean_rtt],
    y=[0, max(hist_counts)],
    mode='lines',
    line=dict(color='green', dash='dash'),
    name=f'Mean: {mean_rtt:.2f} {unit_label}'
))

# Median line
fig.add_trace(go.Scatter(
    x=[median_rtt, median_rtt],
    y=[0, max(hist_counts)],
    mode='lines',
    line=dict(color='purple', dash='dot'),
    name=f'Median: {median_rtt:.2f} {unit_label}'
))

# 99th percentile line
p99 = percentiles[8]
fig.add_trace(go.Scatter(
    x=[p99, p99],
    y=[0, max(hist_counts)],
    mode='lines',
    line=dict(color='orange', dash='dash'),
    name=f'99th percentile: {p99:.2f} {unit_label}'
))

# Layout
fig.update_layout(
    title=f"Data Center RTT Distribution ({unit_label})",
    xaxis_title=f"RTT ({unit_label})",
    yaxis_title="Packet Count",
    template='plotly_white',
    bargap=0.05
)

# Save interactive HTML
fig.write_html(args.html)
print(f"Interactive plot saved as: {args.html}")

# Show plot
fig.show()
