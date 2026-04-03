#!/usr/bin/env python3
import sys
import os
import numpy as np
import joblib
import matplotlib.pyplot as plt
from sklearn.mixture import GaussianMixture

# =====================================================================
# CONFIGURATION
# =====================================================================
N_SAMPLES = 200000        # High sample count for smooth Monte Carlo integration
COMP_RANGE = range(2, 15) # Range of GMM components to test for new models
MIN_DELAY = 0.0001        # Minimum physical delay (0.1ms)
PLOT_CUTOFF_SECONDS = 1.0 # X-axis limit for the generated plots

def fit_best_gmm(data, name):
    """Fits multiple GMMs and selects the best one using BIC."""
    print(f"[*] Fitting new GMM for {name}...")
    data_fit = data.reshape(-1, 1)
    
    best_gmm = None
    best_bic = np.inf
    
    for n in COMP_RANGE:
        gmm = GaussianMixture(n_components=n, covariance_type='full', random_state=42)
        gmm.fit(data_fit)
        bic = gmm.bic(data_fit)
        if bic < best_bic:
            best_bic = bic
            best_gmm = gmm
            
    print(f"  [+] {name} fitted optimally with {best_gmm.n_components} components.")
    return best_gmm

def derive_node_model(total_gmm, rest_gmm):
    """
    Deconvolution via Quantile Subtraction.
    Aligns the CDFs of the Total and Rest models to extract the true Node delay.
    """
    print("\n[*] Step 1: Deriving Isolated Node Model (Deconvolution)")
    samples_total = total_gmm.sample(N_SAMPLES)[0].flatten()
    samples_rest = rest_gmm.sample(N_SAMPLES)[0].flatten()
    
    # Sort to align quantiles
    samples_total.sort()
    samples_rest.sort()
    
    # Subtract to find the delta (Node Delay)
    node_delays = samples_total - samples_rest
    
    # Filter out physical impossibilities (negative time)
    valid_node_delays = node_delays[node_delays > MIN_DELAY]
    
    if len(valid_node_delays) < N_SAMPLES * 0.5:
        print("[!] Warning: High overlap between Total and Rest. Node delay might be negligible.")
        
    return fit_best_gmm(valid_node_delays, "Isolated Node")

def reconstruct_total_model(rest_gmm, node_gmm):
    """
    Convolution via Independent Monte Carlo Addition.
    Adds the isolated node back to the rest of the network to simulate the total pipeline.
    """
    print("\n[*] Step 2: Reconstructing Total Model (Convolution)")
    samples_rest = rest_gmm.sample(N_SAMPLES)[0].flatten()
    samples_node = node_gmm.sample(N_SAMPLES)[0].flatten()
    
    # Shuffle to ensure independent addition (removing any quantile correlation)
    np.random.shuffle(samples_rest)
    np.random.shuffle(samples_node)
    
    reconstructed_delays = samples_rest + samples_node
    
    return fit_best_gmm(reconstructed_delays, "Reconstructed Total")

def calculate_kl_divergence(gmm_p, gmm_q):
    """Calculates D_KL(P || Q) via Monte Carlo."""
    samples_p = gmm_p.sample(N_SAMPLES)[0]
    log_prob_p = gmm_p.score_samples(samples_p)
    log_prob_q = gmm_q.score_samples(samples_p)
    return max(0.0, np.mean(log_prob_p - log_prob_q))

def calculate_symmetric_divergence(gmm_p, gmm_q):
    """Calculates symmetric KL Divergence."""
    kl_p_q = calculate_kl_divergence(gmm_p, gmm_q)
    kl_q_p = calculate_kl_divergence(gmm_q, gmm_p)
    return (kl_p_q + kl_q_p) / 2.0

def plot_pipeline_results(total_gmm, rest_gmm, node_gmm, recon_gmm, output_filename):
    """Generates a 2-panel plot illustrating the Deconvolution and Convolution."""
    print(f"\n[*] Generating Visualization Dashboard...")
    
    x_sec = np.linspace(0, PLOT_CUTOFF_SECONDS, 2000).reshape(-1, 1)
    x_ms = x_sec * 1000.0

    # Calculate Probability Densities (Scale by 1000 to match ms X-axis)
    pdf_total = np.exp(total_gmm.score_samples(x_sec)) / 1000.0
    pdf_rest  = np.exp(rest_gmm.score_samples(x_sec)) / 1000.0
    pdf_node  = np.exp(node_gmm.score_samples(x_sec)) / 1000.0
    pdf_recon = np.exp(recon_gmm.score_samples(x_sec)) / 1000.0

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

    # --- TOP PANEL: Deconvolution (The Parts) ---
    ax1.plot(x_ms, pdf_rest, color='#ff7f0e', lw=2, label='Rest of Network (Input)')
    ax1.fill_between(x_ms.flatten(), 0, pdf_rest, alpha=0.3, color='#ff7f0e')
    
    ax1.plot(x_ms, pdf_node, color='#2ca02c', lw=2, label='Derived Isolated Node (Calculated)')
    ax1.fill_between(x_ms.flatten(), 0, pdf_node, alpha=0.3, color='#2ca02c')
    
    ax1.set_title('Step 1: Deconvolution (Isolated Component Pipelines)', fontsize=14, fontweight='bold')
    ax1.set_xlabel('Latency (Milliseconds)', fontsize=12)
    ax1.set_ylabel('Probability Density', fontsize=12)
    ax1.set_xlim(0, PLOT_CUTOFF_SECONDS * 1000)
    ax1.grid(alpha=0.3, linestyle=':')
    ax1.legend(fontsize=11)

    # --- BOTTOM PANEL: Convolution Validation (The Whole) ---
    ax2.plot(x_ms, pdf_total, color='#1f77b4', lw=2.5, label='Original Total Delay (Baseline)')
    ax2.fill_between(x_ms.flatten(), 0, pdf_total, alpha=0.3, color='#1f77b4')
    
    ax2.plot(x_ms, pdf_recon, color='#d62728', lw=2.5, linestyle='--', label='Reconstructed Total Delay (Convolution)')
    ax2.fill_between(x_ms.flatten(), 0, pdf_recon, alpha=0.2, color='#d62728')
    
    ax2.set_title('Step 2: Convolution Validation (Reality vs. Reconstructed Math)', fontsize=14, fontweight='bold')
    ax2.set_xlabel('Latency (Milliseconds)', fontsize=12)
    ax2.set_ylabel('Probability Density', fontsize=12)
    ax2.set_xlim(0, PLOT_CUTOFF_SECONDS * 1000)
    ax2.grid(alpha=0.3, linestyle=':')
    ax2.legend(fontsize=11)

    plt.tight_layout()
    plt.savefig(output_filename, dpi=300)
    print(f"  [+] Saved plot to: {output_filename}")
    plt.close()

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python3 verify_pipeline.py <total_model.pkl> <rest_model.pkl> <output_node_model.pkl> [output_plot.png]")
        sys.exit(1)

    TOTAL_MODEL_PATH = sys.argv[1]
    REST_MODEL_PATH = sys.argv[2]
    OUTPUT_NODE_PATH = sys.argv[3]
    
    # Auto-generate image name if not provided
    if len(sys.argv) >= 5:
        PLOT_OUTPUT_PATH = sys.argv[4]
    else:
        node_name = os.path.basename(OUTPUT_NODE_PATH).split('_')[0]
        PLOT_OUTPUT_PATH = f"{node_name}_pipeline_validation.png"

    try:
        # Load Inputs
        print(f"[*] Loading Total Baseline Model: {TOTAL_MODEL_PATH}")
        total_gmm = joblib.load(TOTAL_MODEL_PATH)
        
        print(f"[*] Loading Rest-of-System Model: {REST_MODEL_PATH}")
        rest_gmm = joblib.load(REST_MODEL_PATH)
        
        # Step 1: Isolate the target node
        node_gmm = derive_node_model(total_gmm, rest_gmm)
        joblib.dump(node_gmm, OUTPUT_NODE_PATH)
        print(f"  [+] Saved derived node model to {OUTPUT_NODE_PATH}")
        
        # Step 2: Reconstruct the total pipeline
        reconstructed_gmm = reconstruct_total_model(rest_gmm, node_gmm)
        
        # Step 3: Mathematical Validation
        print("\n[*] Step 3: Validating Pipeline Accuracy...")
        kl_score = calculate_kl_divergence(total_gmm, reconstructed_gmm)
        sym_score = calculate_symmetric_divergence(total_gmm, reconstructed_gmm)
        
        print("\n" + "="*60)
        print("    PIPELINE RECONSTRUCTION & VALIDATION RESULTS")
        print("="*60)
        print(f" Original Total:      {TOTAL_MODEL_PATH}")
        print(f" Derived Node Output: {OUTPUT_NODE_PATH}")
        print("-" * 60)
        print(f" KL Divergence (Original || Reconstructed): {kl_score:.4f} nats")
        print(f" Symmetric Distance Score:                  {sym_score:.4f} nats")
        print("-" * 60)
        
        if sym_score < 0.1:
            print("[+] Status: PERFECT. Convolution math holds entirely.")
        elif sym_score < 0.5:
            print("[~] Status: GOOD. Minor variance loss during deconvolution.")
        else:
            print("[-] Status: DRIFT DETECTED. Check if node logic is highly correlated to payload size.")
            
        # Step 4: Generate Plot
        plot_pipeline_results(total_gmm, rest_gmm, node_gmm, reconstructed_gmm, PLOT_OUTPUT_PATH)
            
    except Exception as e:
        print(f"[!] Critical Error: {e}")