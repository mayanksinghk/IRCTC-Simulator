#!/usr/bin/env python3
import sys
import os
from pathlib import Path
import numpy as np
import joblib
import matplotlib.pyplot as plt
from sklearn.mixture import GaussianMixture
from scipy.stats import norm, entropy
from scipy.spatial.distance import jensenshannon

# ==========================================
# CONFIGURATION
# ==========================================
N_SAMPLES = 200000        # Samples for Monte Carlo math
MIN_DELAY = 0.0001        # Minimum threshold (0.1ms) to drop impossible negative times
COMP_RANGE = range(2, 12) # Range to search for the best Difference GMM components
OUTPUT_DIR = "output"     # Target folder for all generated files

def calculate_divergence_metrics(gmm1, gmm2, max_val=1.0):
    """
    Calculates KL-Divergence and JS-Distance between the two INPUT models.
    """
    x_grid = np.linspace(0.0001, max_val, 5000).reshape(-1, 1)
    
    p_pdf = np.exp(gmm1.score_samples(x_grid))
    q_pdf = np.exp(gmm2.score_samples(x_grid))
    
    p_norm = p_pdf / np.sum(p_pdf)
    q_norm = q_pdf / np.sum(q_pdf)
    
    epsilon = 1e-10
    p_norm = np.clip(p_norm, epsilon, 1.0)
    q_norm = np.clip(q_norm, epsilon, 1.0)
    
    kl_div = entropy(p_norm, q_norm)
    js_dist = jensenshannon(p_norm, q_norm)
    
    return kl_div, js_dist

def fit_difference_gmm(diff_data):
    """Finds the optimal GMM for the subtracted data using BIC."""
    print("[*] Fitting new GMM to the isolated difference...")
    data_fit = diff_data.reshape(-1, 1)
    
    best_gmm = None
    best_bic = np.inf
    
    for n in COMP_RANGE:
        gmm = GaussianMixture(n_components=n, covariance_type='full', random_state=42)
        gmm.fit(data_fit)
        bic = gmm.bic(data_fit)
        print(f"  > Testing k={n:<2} | BIC={bic:.2f}")
        if bic < best_bic:
            best_bic = bic
            best_gmm = gmm
            
    print(f"[+] Optimal Difference GMM selected with {best_gmm.n_components} components.")
    return best_gmm

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 calculate_gmm_difference.py <Model_1_Total.pkl> <Model_2_Rest.pkl>")
        sys.exit(1)

    m1_path = sys.argv[1]
    m2_path = sys.argv[2]

    # --- SETUP OUTPUT DIRECTORY & FILENAMES ---
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    # Extract the base name of the first input (e.g., 'path/to/waf_total.pkl' -> 'waf_total')
    base_name = Path(m1_path).stem
    
    print(f"[*] Base prefix for outputs: '{base_name}'")

    # 1. Load Inputs
    print(f"[*] Loading Input 1 (Total): {m1_path}")
    gmm_total = joblib.load(m1_path)
    
    print(f"[*] Loading Input 2 (Rest):  {m2_path}")
    gmm_rest = joblib.load(m2_path)

    # 2. Compare the Initial Input Models
    print("\n[*] Calculating Divergence between Initial Inputs...")
    test_samples = gmm_total.sample(10000)[0]
    dynamic_max = np.percentile(test_samples, 99.5) 
    
    kl_val, js_val = calculate_divergence_metrics(gmm_total, gmm_rest, max_val=dynamic_max)
    print("="*50)
    print("    INPUT COMPARISON METRICS (Total vs Rest)")
    print("="*50)
    print(f" KL-Divergence:           {kl_val:.4f} nats")
    print(f" Jensen-Shannon Distance: {js_val:.4f} (0=Identical, 1=Disjoint)")
    print("="*50)

    # 3. Calculate the Difference (Deconvolution via Quantile Subtraction)
    print("\n[*] Performing Monte Carlo Quantile Subtraction...")
    samples_total = gmm_total.sample(N_SAMPLES)[0].flatten()
    samples_rest = gmm_rest.sample(N_SAMPLES)[0].flatten()
    
    samples_total.sort()
    samples_rest.sort()
    
    raw_diff = samples_total - samples_rest
    valid_diff = raw_diff[raw_diff > MIN_DELAY] 
    
    dropped_pct = (1.0 - (len(valid_diff) / float(N_SAMPLES))) * 100
    print(f"[*] Dropped {dropped_pct:.2f}% of samples due to negative/zero values.")

    # 4. Fit and Save the Difference GMM
    diff_gmm = fit_difference_gmm(valid_diff)
    
    # Save model using dynamic prefix
    out_model_name = os.path.join(OUTPUT_DIR, f"{base_name}_difference_model.pkl")
    joblib.dump(diff_gmm, out_model_name)
    print(f"[+] Saved newly calculated Difference GMM to: {out_model_name}")

    # ==========================================
    # PLOTTING
    # ==========================================
    print("\n[*] Generating requested plots...")
    plot_max_sec = np.percentile(valid_diff, 99.0) 
    x_sec = np.linspace(0.0001, plot_max_sec, 2000).reshape(-1, 1)
    x_ms = x_sec * 1000.0
    
    pdf_diff = np.exp(diff_gmm.score_samples(x_sec)) / 1000.0 
    valid_diff_ms = valid_diff * 1000.0

    # PLOT 1: Difference Probability Distribution
    plt.figure(figsize=(10, 6))
    counts, bin_edges = np.histogram(valid_diff_ms, bins=200, density=True, range=(0, plot_max_sec*1000))
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    plt.fill_between(bin_centers, 0, counts, color='gray', alpha=0.4, label='Raw Subtracted Data')
    plt.plot(x_ms, pdf_diff, color='red', lw=2.5, label='Fitted Difference GMM')
    
    plt.title(f'Difference Distribution ({base_name})', fontsize=14)
    plt.xlabel('Latency Difference (Milliseconds)')
    plt.ylabel('Probability Density')
    plt.legend()
    plt.grid(alpha=0.3)
    plt.tight_layout()
    
    plot1_path = os.path.join(OUTPUT_DIR, f"{base_name}_diff_distribution.png")
    plt.savefig(plot1_path, dpi=300)
    print(f"  [+] Saved Plot 1: {plot1_path}")
    plt.close()

    # PLOT 2: Components of the Difference GMM
    plt.figure(figsize=(10, 6))
    plt.plot(x_ms, pdf_diff, color='black', lw=2, linestyle='--', label='Total Difference Model')
    
    responsibilities = diff_gmm.predict_proba(x_sec)
    individual_pdfs = responsibilities * (pdf_diff[:, np.newaxis])
    colors = plt.cm.tab10.colors
    
    means_ms = diff_gmm.means_.flatten() * 1000.0
    weights = diff_gmm.weights_.flatten()

    for i in range(diff_gmm.n_components):
        plt.fill_between(x_ms.flatten(), 0, individual_pdfs[:, i], alpha=0.5, color=colors[i % len(colors)],
                         label=f'Comp {i+1} (W: {weights[i]*100:.1f}%, Mean: {means_ms[i]:.1f}ms)')
                         
    plt.title(f'Difference Components ({base_name})', fontsize=14)
    plt.xlabel('Latency Difference (Milliseconds)')
    plt.ylabel('Probability Density')
    plt.legend(loc='upper right')
    plt.grid(alpha=0.3)
    plt.tight_layout()
    
    plot2_path = os.path.join(OUTPUT_DIR, f"{base_name}_diff_components.png")
    plt.savefig(plot2_path, dpi=300)
    print(f"  [+] Saved Plot 2: {plot2_path}")
    plt.close()

    print("\n[+] Done.")

if __name__ == "__main__":
    main()