#! /usr/bin/env python3
import pickle
import joblib 
import numpy as np
import matplotlib.pyplot as plt
import sys

def process_gmm_pkl(pkl_filename, output_txt="clean_gmm_latencies.txt", threshold=0.05):
    print(f"Loading GMM from {pkl_filename}...")
    
    # 1. LOAD THE GMM 
    try:
        gmm = joblib.load(pkl_filename)
    except FileNotFoundError:
        print(f"Error: Could not find '{pkl_filename}'")
        sys.exit(1)
    except Exception as e:
        print(f"Joblib failed, trying standard pickle fallback... Error: {e}")
        try:
            with open(pkl_filename, 'rb') as file:
                gmm = pickle.load(file)
        except Exception as e2:
            print(f"Standard pickle also failed: {e2}")
            sys.exit(1)
            
    # 2. EXTRACT PARAMETERS
    weights = gmm.weights_
    
    # --- CONVERSION: Seconds to Milliseconds ---
    # We multiply by 1000 here so the rest of the script is in 'ms'
    means = gmm.means_.flatten() * 1000
    
    # Standard deviation is also in seconds, so it must be scaled by 1000
    stds = np.sqrt(gmm.covariances_).flatten() * 1000

    print(f"\nOriginal GMM had {len(weights)} components (Units converted from sec to ms).")

    # 3. PRUNE AND RE-NORMALIZE
    keep_indices = weights >= threshold
    
    filtered_weights = weights[keep_indices]
    filtered_means = means[keep_indices]
    filtered_stds = stds[keep_indices]

    final_weights = filtered_weights / np.sum(filtered_weights)

    print(f"Pruned to {len(final_weights)} dominant components (threshold: {threshold*100}%).")
    for i in range(len(final_weights)):
        print(f"  Component {i+1}: Weight={final_weights[i]:.3f}, Mean={filtered_means[i]:.2f}ms, StdDev={filtered_stds[i]:.2f}ms")

    # 4. GENERATE TRUNCATED SAMPLES (NO NEGATIVES)
    target_samples = 1000000 
    valid_samples = []
    print("\nGenerating 1,000,000 samples and enforcing physical reality (Latencies >= 0)...")

    while len(valid_samples) < target_samples:
        components = np.random.choice(len(final_weights), size=20000, p=final_weights)
        batch_samples = np.random.normal(loc=filtered_means[components], 
                                         scale=filtered_stds[components])
        
        positive_samples = batch_samples[batch_samples >= 0]
        valid_samples.extend(positive_samples)

    final_latencies = np.array(valid_samples[:target_samples])

    # CALCULATE OVERALL MEAN AND JITTER (Now accurately in ms)
    overall_mean = np.mean(final_latencies)
    overall_jitter = np.std(final_latencies)

    # 5. EXPORT FOR LINUX 'maketable'
    print(f"Saving clean data to '{output_txt}'...")
    # Note: These values are now saved as ms values (e.g. 50.0 instead of 0.050)
    np.savetxt(output_txt, final_latencies, fmt='%.4f')

    # 6. VERIFICATION PLOT & INSTRUCTIONS
    plt.figure(figsize=(10, 5))
    plt.hist(final_latencies, bins=300, density=True, color='#3498db', alpha=0.7)
    plt.title("Pruned & Truncated GMM (Units: Milliseconds)")
    plt.xlabel("Latency (ms)")
    plt.ylabel("Density")
    plt.xlim(0, max(filtered_means) + max(filtered_stds)*3)
    plt.grid(True, alpha=0.3)
    
    plot_name = "pruned_gmm_verification.png"
    plt.savefig(plot_name, dpi=300)
    print(f"Saved verification plot to '{plot_name}'")
    
    print("\n" + "="*60)
    print("SUCCESS! YOUR MININET PARAMETERS ARE READY.")
    print("="*60)
    print("Step 1: Generate the .dist file (Run this in terminal):")
    print(f"  /home/mayank/Application/iproute2/netem/maketable < {output_txt} > app.dist")
    print("\nStep 2: Apply to your interface using these calculated values:")
    print(f"  Overall Mean:   {overall_mean:.2f}ms")
    print(f"  Overall Jitter: {overall_jitter:.2f}ms")
    print("\nExample tc command:")
    print(f"  tc qdisc add dev server-eth0 root netem delay {overall_mean:.2f}ms {overall_jitter:.2f}ms distribution app")
    print("="*60 + "\n")

if __name__ == "__main__":
    YOUR_PKL_FILE = "12_model_mode2.pkl" 
    process_gmm_pkl(YOUR_PKL_FILE)