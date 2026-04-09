#!/usr/bin/env python3
import os
import sys
import subprocess
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.mixture import GaussianMixture
from pathlib import Path
import joblib 
from scipy.stats import norm

# ================= CONFIGURATION =================
SAMPLE_SIZE = 1000000              
COMP_RANGE = range(2, 30)          
SAMPLES_PER_COMP = 10              
PLOT_CUTOFF_SECONDS = 1          
# =================================================

def pre_process_pcap(infile, outfile, mode):
    """Filters traffic based on mode with robust decoding and desegmentation."""
    if os.path.exists(outfile):
        print(f"[*] {outfile} already exists. Skipping.")
        return
    
    # Mode 1: TLS (Content type 23 or Port 443)
    # Mode 2: HTTP
    if mode == 1:
        display_filter = "tls.record.content_type == 23 || tcp.port == 443"
        decode_param = ['-d', 'tcp.port==443,tls'] 
    else:
        display_filter = "http || tcp.port == 80"
        decode_param = []
    
    print(f"[*] Pre-processing (Mode {mode}): Filtering {infile}...")
    
    # Forced desegmentation ensures we don't miss split application data records
    cmd = ['tshark', '-r', infile] + decode_param + [
        '-Y', display_filter,
        '-o', 'tls.desegment_ssl_records:TRUE',
        '-o', 'tcp.desegment_tcp_streams:TRUE',
        '-w', outfile
    ]
    subprocess.run(cmd, check=True)

def extract_metadata(pcap_path, csv_out, mode):
    """Extracts delay. Mode 1 calculates TLS delta; Mode 2 uses http.time."""
    if os.path.exists(csv_out):
        print(f"[*] {csv_out} exists. Skipping.")
        return

    if mode == 2:
        # Standard HTTP Extraction
        cmd = [
            'tshark', '-r', pcap_path, '-Y', 'http.response', 
            '-T', 'fields', '-e', 'frame.number', '-e', 'http.request_in', '-e', 'http.time',
            '-E', 'separator=,'
        ]
        with open(csv_out, 'w') as f:
            subprocess.run(cmd, stdout=f, check=True)
    
    else:
        # TLS Manual Calculation (No Decryption)
        SERVER_PORT = "443" 
        print(f"[*] Calculating TLS equivalent of http.time via stream analysis (Port {SERVER_PORT})...")
        
        # Includes tcp.len to distinguish between ACKs and Application Data
        cmd = [
            'tshark', '-r', pcap_path, 
            '-T', 'fields', '-e', 'frame.number', '-e', 'frame.time_epoch', 
            '-e', 'tcp.stream', '-e', 'tcp.srcport', '-e', 'tcp.dstport', '-e', 'tcp.len',
            '-E', 'separator=,'
        ]
        
        try:
            raw_data = subprocess.check_output(cmd).decode('utf-8').splitlines()
        except subprocess.CalledProcessError as e:
            print(f"[!] TShark Error: {e}")
            return

        results = []
        streams = {} 

        for line in raw_data:
            if not line.strip(): continue
            parts = line.split(',')
            
            if len(parts) < 6 or not parts[3] or not parts[4] or not parts[5]: 
                continue 
                
            f_num, f_time, s_id, src_port, dst_port, tcp_len = parts
            f_time = float(f_time)
            
            try:
                payload_size = int(tcp_len)
            except ValueError:
                continue

            # Skip pure ACKs
            if payload_size == 0:
                continue
            
            if dst_port == SERVER_PORT:
                direction = 'C->S' 
            elif src_port == SERVER_PORT:
                direction = 'S->C' 
            else:
                continue 
                
            if s_id not in streams:
                streams[s_id] = {'last_dir': None, 'last_client_time': None, 'last_req_frame': None}
                
            flow = streams[s_id]
            
            if direction == 'C->S':
                flow['last_client_time'] = f_time
                flow['last_req_frame'] = f_num
                flow['last_dir'] = 'C->S'
                
            elif direction == 'S->C':
                if flow['last_dir'] == 'C->S' and flow['last_client_time'] is not None:
                    delay = f_time - flow['last_client_time']
                    if 0.0005 < delay < 5.0: 
                        results.append(f"{f_num},{flow['last_req_frame']},{delay:.6f}")
                flow['last_dir'] = 'S->C'
        
        with open(csv_out, 'w') as f:
            f.write("\n".join(results))

def run_gmm_analysis(csv_path):
    print("[*] Loading metadata...")
    try:
        df = pd.read_csv(csv_path, names=['res_frame', 'req_frame', 'delay'])
    except Exception:
        print(f"[!] Could not read {csv_path}. File may be empty.")
        return None, None

    df = df[(df['delay'] > 0.0) & (df['delay'] < 5.0)].dropna() 
    
    if len(df) < 2:
        print(f"[!] Insufficient data in {csv_path} (minimum 2 samples required).")
        return None, None 

    data_fit = df['delay'].values.reshape(-1, 1)
    
    bic_scores = []
    models = []
    for n in COMP_RANGE:
        gmm = GaussianMixture(n_components=n, covariance_type='full', random_state=42)
        gmm.fit(data_fit)
        bic_scores.append(gmm.bic(data_fit))
        models.append(gmm)
        print(f"  > n={n:<2} | BIC={bic_scores[-1]:.2f}")

    best_gmm = models[np.argmin(bic_scores)]
    df['component'] = best_gmm.predict(data_fit)
    return best_gmm, df

def plot_separated_models(gmm, df_sample, output_dir, pcap_basename, mode):
    print("\n[*] Generating Validation Plots (Scaled to Milliseconds)...")
    data_ms = df_sample['delay'].values * 1000.0
    max_plot_ms = PLOT_CUTOFF_SECONDS * 1000.0
    
    # X-axis generation for continuous lines
    x_seconds = np.linspace(0, PLOT_CUTOFF_SECONDS, 2000).reshape(-1, 1)
    x_ms = x_seconds * 1000.0
    
    # GMM PDF Calculation
    pdf_total_ms = np.exp(gmm.score_samples(x_seconds)) / 1000.0
    
    # ==========================================
    # Plot 1: Total Distribution (PDF Comparison)
    # ==========================================
    plt.figure(figsize=(12, 6))
    
    # Calculate empirical PDF from raw data to plot as a solid line (instead of bars)
    counts, bin_edges = np.histogram(data_ms, bins='auto', density=True, range=(0, max_plot_ms))
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    
    # Plot Raw PCAP as Solid Line
    plt.plot(bin_centers, counts, color='gray', lw=2, label='Raw PCAP Distribution')
    
    # Plot GMM as Dashed Line
    plt.plot(x_ms, pdf_total_ms, color='red', lw=2.5, linestyle='--', label='Total GMM Model')
    
    plt.title(f'{pcap_basename} (Mode {mode}) - PDF: Reality vs. GMM')
    plt.xlabel('Latency (Milliseconds)')
    plt.ylabel('Probability Density')
    plt.legend()
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(output_dir, f"{pcap_basename}_mode{mode}_distribution.png"))
    plt.close()

    # ==========================================
    # Plot 2: Components
    # ==========================================
    plt.figure(figsize=(12, 6))
    responsibilities = gmm.predict_proba(x_seconds)
    individual_pdfs_ms = responsibilities * pdf_total_ms[:, np.newaxis]
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
    
    for i in range(gmm.n_components):
        plt.fill_between(x_ms.flatten(), 0, individual_pdfs_ms[:, i], alpha=0.5, color=colors[i % len(colors)],
                         label=f'Comp {i+1} (Mean: {gmm.means_[i][0]*1000:.1f}ms)')
    plt.title(f'{pcap_basename} (Mode {mode}) - Component Pathways')
    plt.legend(loc='upper right')
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(output_dir, f"{pcap_basename}_mode{mode}_components.png"))
    plt.close()

    # ==========================================
    # Plot 3: Cumulative Distribution (CDF Comparison)
    # ==========================================
    plt.figure(figsize=(12, 6))
    
    # 1. Raw PCAP CDF (Solid Line)
    # Filter sorted data to match our plot cutoff window
    sorted_data = np.sort(data_ms)
    sorted_data_filtered = sorted_data[sorted_data <= max_plot_ms]
    y_ecdf = np.arange(1, len(sorted_data_filtered) + 1) / len(sorted_data_filtered)
    
    plt.plot(sorted_data_filtered, y_ecdf, color='blue', lw=2.5, label='Raw PCAP CDF')

    # 2. GMM CDF (Dashed Line)
    weights = gmm.weights_
    means_ms = gmm.means_.flatten() * 1000.0
    stds_ms = np.sqrt(gmm.covariances_).flatten() * 1000.0
    
    Y_total_cdf = np.zeros_like(x_ms).flatten()
    for i in range(gmm.n_components):
        comp_cdf = weights[i] * norm.cdf(x_ms.flatten(), loc=means_ms[i], scale=stds_ms[i])
        Y_total_cdf += comp_cdf
        
    plt.plot(x_ms.flatten(), Y_total_cdf, color='red', lw=3, linestyle='--', label='Total GMM CDF')

    plt.title(f'{pcap_basename} (Mode {mode}) - CDF: Reality vs. GMM')
    plt.xlabel('Latency (Milliseconds)')
    plt.ylabel('Cumulative Probability')
    plt.legend(loc='lower right')
    plt.grid(True, alpha=0.3)
    plt.savefig(os.path.join(output_dir, f"{pcap_basename}_mode{mode}_cdf.png"))
    plt.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python full_gmm.py <pcap_file> <mode>")
        sys.exit(1)

    INPUT_PCAP = sys.argv[1]
    MODE = int(sys.argv[2])
    
    pcap_basename = Path(INPUT_PCAP).name.split('.')[0]
    output_dir = Path(pcap_basename)
    output_dir.mkdir(parents=True, exist_ok=True)

    LEAN_PCAP = str(output_dir / f"{pcap_basename}_mode{MODE}_filtered.pcap")
    METADATA_CSV = str(output_dir / f"{pcap_basename}_mode{MODE}_latency.csv")
    model_filename = str(output_dir / f"{pcap_basename}_model_mode{MODE}.pkl")

    pre_process_pcap(INPUT_PCAP, LEAN_PCAP, MODE)
    extract_metadata(LEAN_PCAP, METADATA_CSV, MODE)
    
    best_model, results_df = run_gmm_analysis(METADATA_CSV)
    
    if best_model:
        joblib.dump(best_model, model_filename)
        print(f"\n[+] Model saved to: {model_filename}")
        plot_separated_models(best_model, results_df, str(output_dir), pcap_basename, MODE)