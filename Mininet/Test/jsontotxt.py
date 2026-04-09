#!/usr/bin/env python3
import json
import statistics
import argparse

def main():
    # Set your Mininet baseline here (in milliseconds)
    MININET_BASELINE_MS = 0.022 
    
    input_json = 'delay.json'
    output_txt = 'delays.txt'

    print(f"[*] Reading {input_json}...")
    try:
        with open(input_json, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"[!] Error: {input_json} not found.")
        return

    delays_seconds = data.get("delays_seconds", [])
    if not delays_seconds:
        print("[!] Error: No data found.")
        return

    # List to hold the final numbers we feed to maketable
    adjusted_delays = []

    with open(output_txt, 'w') as f:
        for delay_sec in delays_seconds:
            # 1. Convert PCAP seconds to milliseconds
            delay_ms = delay_sec * 1000.0
            
            # 2. Subtract baseline and prevent negative values
            adjusted_delay = max(0.0, delay_ms - MININET_BASELINE_MS)
            adjusted_delays.append(adjusted_delay)
            
            # 3. Write to text file
            f.write(f"{adjusted_delay}\n")

    # ==========================================
    # CALCULATE MEAN AND JITTER
    # ==========================================
    # Mean is the average of the adjusted values
    mean_ms = statistics.mean(adjusted_delays)
    
    # Jitter (in tc netem) is best represented by the Standard Deviation
    # If all values are the exact same, stdev is 0
    if len(adjusted_delays) > 1:
        jitter_ms = statistics.stdev(adjusted_delays)
    else:
        jitter_ms = 0.0

    print(f"[*] Successfully wrote adjusted distributions to {output_txt}")
    print("\n" + "="*50)
    print("🎯 YOUR TC NETEM METRICS 🎯")
    print(f"Calculated Mean:   {mean_ms:.2f}ms")
    print(f"Calculated Jitter: {jitter_ms:.2f}ms")
    print("="*50)
    
    print("\nNext steps:")
    print("1. Compile:  ./maketable < delays.txt > app.dist")
    print(f"2. Mininet Command:  tc qdisc add dev server-eth0 root netem delay {mean_ms:.2f}ms {jitter_ms:.2f}ms distribution app")

if __name__ == "__main__":
    main()