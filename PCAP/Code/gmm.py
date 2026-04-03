#!/usr/bin/env python3
import os
import subprocess
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.mixture import GaussianMixture

# ================= CONFIGURATION =================
INPUT_PCAP = "./../10.pcap"        # Original 10GB file
HTTP_ONLY_PCAP = "irctc_http_only.pcap"  # Pre-processed lean file
METADATA_CSV = "http_metadata.csv"       # Frame mapping

SAMPLE_SIZE = 1000000                    # Statistical packet limit
COMP_RANGE = range(2, 25)                # BIC search range
SAMPLES_PER_COMP = 10                    # Pairs per component (10 req + 10 res)

# --- NEW PLOT VARIABLES ---
PLOT_CUTOFF_SECONDS = 2.0                # Variable to cut the plot at X seconds
# =================================================

def pre_process_pcap(infile, outfile):
    """Filters the 10GB file to keep only HTTP traffic. Huge speed boost."""
    if os.path.exists(outfile):
        print(f"[*] {outfile} already exists. Skipping pre-processing.")
        return
    print(f"[*] Pre-processing: Stripping non-HTTP traffic from {infile}...")
    cmd = ['tshark', '-r', infile, '-Y', 'http', '-w', outfile, '-2']
    subprocess.run(cmd, check=True)
    print(f"[+] Lean PCAP created: {outfile}")

def extract_http_metadata(pcap_path, csv_out):
    """Extracts Response Frame, Request Frame, and the Delay (http.time)"""
    if os.path.exists(csv_out):
        print(f"[*] {csv_out} already exists. Skipping extraction.")
        return

    print(f"[*] Extracting Request-Response metadata from {pcap_path}...")
    cmd = [
        'tshark', '-r', pcap_path,
        '-Y', 'http.response', 
        '-T', 'fields', 
        '-e', 'frame.number',
        '-e', 'http.request_in',
        '-e', 'http.time',
        '-E', 'separator=,'
    ]
    
    with open(csv_out, 'w') as f:
        subprocess.run(cmd, stdout=f, check=True)
    print(f"[+] Metadata saved to {csv_out}")

def run_gmm_analysis(csv_path):
    print("[*] Loading and cleaning metadata...")
    df = pd.read_csv(csv_path, names=['res_frame', 'req_frame', 'delay'], 
                     dtype={'res_frame': np.float64, 'req_frame': np.float64, 'delay': np.float32})
    
    # Filter valid delays
    df = df[(df['delay'] > 0) & (df['delay'] < 5.0)].dropna()
    
    # Convert frames to int after dropping NaNs
    df['res_frame'] = df['res_frame'].astype(np.int64)
    df['req_frame'] = df['req_frame'].astype(np.int64)
    
    df_sample = df.sample(n=min(len(df), SAMPLE_SIZE), random_state=42)
    data_fit = df_sample['delay'].values.reshape(-1, 1)

    print(f"[*] Grid Searching optimal GMM...")
    bic_scores = []
    models = []
    for n in COMP_RANGE:
        gmm = GaussianMixture(n_components=n, covariance_type='full', random_state=42)
        gmm.fit(data_fit)
        bic_scores.append(gmm.bic(data_fit))
        models.append(gmm)
        print(f"  > n={n:<2} | BIC={bic_scores[-1]:.2f}")

    best_idx = np.argmin(bic_scores)
    best_gmm = models[best_idx]
    df_sample['component'] = best_gmm.predict(data_fit)
    
    return best_gmm, df_sample

def carve_request_response_pairs(pcap_path, df_results, n_components):
    """Extracts matching Request AND Response frames for each component"""
    print("\n[*] Carving Request-Response pairs into sub-PCAPs...")
    
    for i in range(n_components):
        comp_data = df_results[df_results['component'] == i]
        res_frames = comp_data['res_frame'].head(SAMPLES_PER_COMP).tolist()
        req_frames = comp_data['req_frame'].head(SAMPLES_PER_COMP).tolist()
        
        all_frames = sorted(list(set(res_frames + req_frames)))
        if not all_frames: continue
            
        out_pcap = f"comp_{i+1}_transactions.pcap"
        display_filter = " || ".join([f"frame.number=={f}" for f in all_frames])
        
        cmd = ['tshark', '-r', pcap_path, '-Y', display_filter, '-w', out_pcap]
        subprocess.run(cmd, check=True)
        print(f"  [+] Created: {out_pcap} ({len(all_frames)} packets)")

def plot_separated_models(gmm, df_sample):
    print("\n[*] Generating Validation Plots (Scaled to Milliseconds)...")
    
    # 1. Prepare the Data
    data_seconds = df_sample['delay'].values
    data_ms = data_seconds * 1000.0  # Convert reality to ms
    
    max_plot_ms = PLOT_CUTOFF_SECONDS * 1000.0
    n_comp = gmm.n_components
    
    # Generate X-axis values for the Math (in seconds, up to the cutoff)
    x_seconds = np.linspace(0, PLOT_CUTOFF_SECONDS, 2000).reshape(-1, 1)
    x_ms = x_seconds * 1000.0  # Convert X-axis for plotting
    
    # Calculate Probabilities
    log_prob = gmm.score_samples(x_seconds)
    pdf_total_seconds = np.exp(log_prob)
    
    # MATHEMATICAL SCALING: If we stretch X by 1000, we must shrink Y by 1000 
    # so the total area under the curve remains exactly 1.0.
    pdf_total_ms = pdf_total_seconds / 1000.0
    
    # ==========================================================
    # PLOT 1: PCAP Probability Distribution vs Total GMM
    # ==========================================================
    plt.figure(figsize=(12, 6))
    
    # Histogram of reality (Scaled to ms, limited to cutoff)
    plt.hist(data_ms, bins=1000, density=True, alpha=0.5, color='gray', 
             label='Raw PCAP Distribution', range=(0, max_plot_ms))
    
    # Total GMM Model
    plt.plot(x_ms, pdf_total_ms, color='red', lw=2.5, label='Digital Twin (Total Model)')
    
    plt.title(f'Plot 1: Normalized Reality vs. GMM (Cutoff: {PLOT_CUTOFF_SECONDS}s)', fontsize=14)
    plt.xlabel('HTTP Latency (Milliseconds)', fontsize=12)
    plt.ylabel('Probability Density', fontsize=12)
    plt.xlim(0, max_plot_ms)
    plt.grid(alpha=0.3)
    plt.legend(fontsize=11)
    plt.tight_layout()
    plt.savefig('plot1_pcap_vs_total_ms.png')
    print("  [+] Saved: plot1_pcap_vs_total_ms.png")

    # ==========================================================
    # PLOT 2: Separated Gaussian Components
    # ==========================================================
    plt.figure(figsize=(12, 6))
    
    # Draw the outline
    plt.plot(x_ms, pdf_total_ms, color='black', lw=1.5, linestyle=':', label='Total Model Outline')
    
    # Calculate individual humps
    responsibilities = gmm.predict_proba(x_seconds)
    individual_pdfs_ms = responsibilities * pdf_total_ms[:, np.newaxis]
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2']
    
    for i in range(n_comp):
        color = colors[i % len(colors)]
        mean_ms = gmm.means_[i][0] * 1000.0
        plt.fill_between(x_ms.flatten(), 0, individual_pdfs_ms[:, i], alpha=0.5, color=color,
                         label=f'Comp {i+1} (Mean: {mean_ms:.1f}ms | Wgt: {gmm.weights_[i]:.1%})')

    plt.title('Plot 2: Isolated Component Pathways', fontsize=14)
    plt.xlabel('HTTP Latency (Milliseconds)', fontsize=12)
    plt.ylabel('Probability Density', fontsize=12)
    plt.xlim(0, max_plot_ms)
    plt.grid(alpha=0.3)
    plt.legend(fontsize=10, loc='upper right')
    plt.tight_layout()
    plt.savefig('plot2_gmm_components_ms.png')
    print("  [+] Saved: plot2_gmm_components_ms.png")
    
    # Optionally show plots interactively if running in a GUI
    # plt.show()

if __name__ == "__main__":
    # 1. Pre-process
    pre_process_pcap(INPUT_PCAP, HTTP_ONLY_PCAP)
    
    # 2. Extract Data
    extract_http_metadata(HTTP_ONLY_PCAP, METADATA_CSV)
    
    # 3. Fit Model
    best_model, results_df = run_gmm_analysis(METADATA_CSV)
    
    # 4. Print Summary
    print("\n" + "="*45)
    print(f"DIGITAL TWIN PARAMETERS ({best_model.n_components} Components)")
    print("="*45)
    for i in range(best_model.n_components):
        print(f"Component {i+1}:")
        print(f"  - Mean:     {best_model.means_[i][0]*1000:.2f} ms")
        print(f"  - Variance: {best_model.covariances_[i][0][0]*1000000:.2f} ms²")
        print(f"  - Weight:   {best_model.weights_[i]:.2%}")
    
    # 5. Extract PCAPs
    carve_request_response_pairs(HTTP_ONLY_PCAP, results_df, best_model.n_components)
    
    # 6. Generate ms-scaled plots cut at PLOT_CUTOFF_SECONDS
    plot_separated_models(best_model, results_df)