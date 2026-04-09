#!/usr/bin/env python3
import argparse
import joblib
import numpy as np
import json
import os
import sys

def generate_isolated_delays(total_path, rest_path, num_samples, output_file):
    # 1. Verify and Load the Target Model
    if not os.path.exists(total_path):
        print(f"[X] Error: Total/Target model '{total_path}' not found.")
        sys.exit(1)

    print(f"[*] Loading Target Model: {total_path}")
    total_gmm = joblib.load(total_path)
    
    # Generate initial samples
    print(f"[*] Generating {num_samples} realistic delay samples...")
    total_samples = total_gmm.sample(num_samples * 2)[0].flatten()

    # 2. Check if a "Rest of Network" model exists
    if rest_path and rest_path.upper() != "NONE":
        if not os.path.exists(rest_path):
            print(f"[X] Error: Rest model '{rest_path}' not found.")
            sys.exit(1)
            
        print(f"[*] Loading Rest Model:   {rest_path}")
        rest_gmm = joblib.load(rest_path)
        
        # Sample and subtract (N = T - R)
        rest_samples = rest_gmm.sample(num_samples * 2)[0].flatten()
        isolated_delays = total_samples - rest_samples
        print("[*] Applied Subtraction: Node = Total - Rest")
    else:
        # App Server Case (Terminal Node)
        print("[*] No Rest Model provided. Assuming terminal node (Node = Target).")
        isolated_delays = total_samples
    
    # 3. Filter impossible physics(all delays must be > 0.001s) and limit to requested sample size
    valid_delays = isolated_delays[isolated_delays > 0.001]
    
    if len(valid_delays) >= num_samples:
        final_pool = valid_delays[:num_samples].tolist()
    else:
        print(f"[!] Warning: High rejection rate. Only extracted {len(valid_delays)} valid samples.")
        final_pool = valid_delays.tolist()
        
    # 4. Save to JSON
    print(f"[*] Saving delays to {output_file}...")
    with open(output_file, 'w') as f:
        json.dump({"delays_seconds": final_pool}, f)
        
    file_size_mb = os.path.getsize(output_file) / (1024 * 1024)
    print(f"[+] Success! {len(final_pool)} delays saved to {output_file} ({file_size_mb:.2f} MB)\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate isolated node delays for Mininet emulators.")
    parser.add_argument("--total", required=True, help="Path to Total Network GMM (.pkl)")
    parser.add_argument("--rest", required=False, default=None, help="Path to Rest of Network GMM (.pkl) or 'NONE'")
    parser.add_argument("--output", default="delays.json", help="Output file name (e.g., delays.json)")
    parser.add_argument("--samples", type=int, default=100000, help="Number of delay samples to generate")
    
    args = parser.parse_args()
    generate_isolated_delays(args.total, args.rest, args.samples, args.output)