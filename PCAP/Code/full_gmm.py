#!/usr/bin/env python3
import os
import sys
import subprocess
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.mixture import GaussianMixture
from pathlib import Path
import joblib  # Added for saving the GMM model

# ================= CONFIGURATION =================
SAMPLE_SIZE = 1000000              
COMP_RANGE = range(2, 30)          
SAMPLES_PER_COMP = 10              
PLOT_CUTOFF_SECONDS = 2.0          
# =================================================

def pre_process_pcap(infile, outfile, mode):
    """Filters traffic based on mode (1=TLS, 2=HTTP)."""
    if os.path.exists(outfile):
        print(f"[*] {outfile} already exists. Skipping.")
        return
    
    # Mode 1: TLS (Content type 23 is Application Data)
    # Mode 2: HTTP
    display_filter = "tls.record.content_type == 23" if mode == 1 else "http"
    
    print(f"[*] Pre-processing ({'TLS' if mode==1 else 'HTTP'}): Filtering {infile}...")
    cmd = ['tshark', '-r', infile, '-Y', display_filter, '-w', outfile, '-2']
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
        # TLS Manual Calculation (No Decryption) - CORRECTED
        SERVER_PORT = "443"  # Set to your target server port (e.g., 443, 8443)
        
        print(f"[*] Calculating TLS equivalent of http.time via stream analysis (Port {SERVER_PORT})...")
        
        # ADDED: tcp.srcport and tcp.dstport to establish absolute direction
        cmd = [
            'tshark', '-r', pcap_path, 
            '-T', 'fields', '-e', 'frame.number', '-e', 'frame.time_epoch', 
            '-e', 'tcp.stream', '-e', 'tcp.srcport', '-e', 'tcp.dstport',
            '-E', 'separator=,'
        ]
        raw_data = subprocess.check_output(cmd).decode('utf-8').splitlines()
        
        results = []
        # Dictionary to hold the state machine for each individual TCP connection
        # Format: stream_id -> {'last_dir': str, 'last_client_time': float, 'last_req_frame': str}
        streams = {} 

        for line in raw_data:
            if not line.strip(): continue
            parts = line.split(',')
            
            # Skip malformed lines or packets missing port data
            if len(parts) != 5 or not parts[3] or not parts[4]: 
                continue 
                
            f_num, f_time, s_id, src_port, dst_port = parts
            f_time = float(f_time)

            # If the TCP payload is 0 bytes, it is a pure ACK. Ignore it completely.
            if int(tcp_len) == 0:
                continue
            
            # 1. Establish Absolute Direction
            if dst_port == SERVER_PORT:
                direction = 'C->S'  # Client is talking to Server
            elif src_port == SERVER_PORT:
                direction = 'S->C'  # Server is replying to Client
            else:
                continue  # Ignore background traffic not matching our server port
                
            # 2. Initialize the stream state if we haven't seen it yet
            if s_id not in streams:
                streams[s_id] = {'last_dir': None, 'last_client_time': None, 'last_req_frame': None}
                
            flow = streams[s_id]
            
            # 3. The Strict State Machine Logic
            if direction == 'C->S':
                # Client is sending data. 
                # Record the timestamp and frame, and set the state to 'C->S'
                flow['last_client_time'] = f_time
                flow['last_req_frame'] = f_num
                flow['last_dir'] = 'C->S'
                
            elif direction == 'S->C':
                # Server is sending data.
                # ONLY calculate latency if the server is actively replying to a client request.
                if flow['last_dir'] == 'C->S' and flow['last_client_time'] is not None:
                    delay = f_time - flow['last_client_time']
                    
                    # Filter out microsecond noise (like immediate TCP window updates/ACKs)
                    if delay > 0.001: 
                        results.append(f"{f_num},{flow['last_req_frame']},{delay:.6f}")
                        
                # Update the state to 'S->C'. 
                # This prevents subsequent server packets from generating false delay calculations.
                flow['last_dir'] = 'S->C'
        
        with open(csv_out, 'w') as f:
            f.write("\n".join(results))

def run_gmm_analysis(csv_path):
    print("[*] Loading metadata...")
    df = pd.read_csv(csv_path, names=['res_frame', 'req_frame', 'delay'])
    df = df[(df['delay'] > 0.001) & (df['delay'] < 5.0)].dropna() # Filter noise/timeouts
    
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

def plot_separated_models(gmm, df_sample, output_dir, pcap_basename):
    print("\n[*] Generating Validation Plots (Scaled to Milliseconds)...")
    
    # Prepare Data
    data_seconds = df_sample['delay'].values
    data_ms = data_seconds * 1000.0  # Convert to ms
    
    max_plot_ms = PLOT_CUTOFF_SECONDS * 1000.0
    n_comp = gmm.n_components
    
    # Generate X-axis values (seconds)
    x_seconds = np.linspace(0, PLOT_CUTOFF_SECONDS, 2000).reshape(-1, 1)
    x_ms = x_seconds * 1000.0
    
    # Calculate Probabilities
    log_prob = gmm.score_samples(x_seconds)
    pdf_total_seconds = np.exp(log_prob)
    pdf_total_ms = pdf_total_seconds / 1000.0
    
    # ==========================================================
    # PLOT 1: PCAP Probability Distribution vs Total GMM
    # ==========================================================
    plt.figure(figsize=(12, 6))
    plt.hist(data_ms, bins=1000, density=True, alpha=0.5, color='gray', 
             label='Raw PCAP Distribution', range=(0, max_plot_ms))
    plt.plot(x_ms, pdf_total_ms, color='red', lw=2.5, label='Total GMM Model')
    
    plt.title(f'{pcap_basename} - Normalized Reality vs. GMM (Cutoff: {PLOT_CUTOFF_SECONDS}s)', fontsize=14)
    plt.xlabel('Latency (Milliseconds)', fontsize=12)
    plt.ylabel('Probability Density', fontsize=12)
    plt.xlim(0, max_plot_ms)
    plt.grid(alpha=0.3)
    plt.legend(fontsize=11)
    plt.tight_layout()
    
    plot1_path = os.path.join(output_dir, f"{pcap_basename}_plot1_distribution.png")
    plt.savefig(plot1_path)
    print(f"  [+] Saved: {plot1_path}")
    plt.close()

    # ==========================================================
    # PLOT 2: Separated Gaussian Components
    # ==========================================================
    plt.figure(figsize=(12, 6))
    plt.plot(x_ms, pdf_total_ms, color='black', lw=1.5, linestyle=':', label='Total Model Outline')
    
    responsibilities = gmm.predict_proba(x_seconds)
    individual_pdfs_ms = responsibilities * pdf_total_ms[:, np.newaxis]
    
    colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2']
    
    for i in range(n_comp):
        color = colors[i % len(colors)]
        mean_ms = gmm.means_[i][0] * 1000.0
        plt.fill_between(x_ms.flatten(), 0, individual_pdfs_ms[:, i], alpha=0.5, color=color,
                         label=f'Comp {i+1} (Mean: {mean_ms:.1f}ms | Wgt: {gmm.weights_[i]:.1%})')

    plt.title(f'{pcap_basename} - Isolated Component Pathways', fontsize=14)
    plt.xlabel('Latency (Milliseconds)', fontsize=12)
    plt.ylabel('Probability Density', fontsize=12)
    plt.xlim(0, max_plot_ms)
    plt.grid(alpha=0.3)
    plt.legend(fontsize=10, loc='upper right')
    plt.tight_layout()
    
    plot2_path = os.path.join(output_dir, f"{pcap_basename}_plot2_components.png")
    plt.savefig(plot2_path)
    print(f"  [+] Saved: {plot2_path}")
    plt.close()

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python irctc_analyzer.py <pcap_file> <mode>")
        print("Modes: 1 = TLS (Encrypted), 2 = HTTP (Plain)")
        sys.exit(1)

    INPUT_PCAP = sys.argv[1]
    MODE = int(sys.argv[2])
    
    # Extract basename (e.g., "10" from "./../10.pcap")
    pcap_basename = Path(INPUT_PCAP).name.split('.')[0]
    
    # Create the output directory based on the pcap basename
    output_dir = Path(pcap_basename)
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n[*] All outputs will be saved to directory: {output_dir}/")

    # Define paths inside the new directory
    LEAN_PCAP = str(output_dir / f"{pcap_basename}_filtered_traffic.pcap")
    METADATA_CSV = str(output_dir / f"{pcap_basename}_latency_metadata.csv")
    model_filename = str(output_dir / f"{pcap_basename}_model_mode{MODE}.pkl")

    # 1. Pre-process
    pre_process_pcap(INPUT_PCAP, LEAN_PCAP, MODE)
    
    # 2. Extract Data
    extract_metadata(LEAN_PCAP, METADATA_CSV, MODE)
    
    # 3. Fit Model
    best_model, results_df = run_gmm_analysis(METADATA_CSV)
    
    # 4. Summary & Output
    print(f"\n[+] Digital Twin Created with {best_model.n_components} pathways.")
    for i in range(best_model.n_components):
        print(f"Path {i+1}: {best_model.means_[i][0]*1000:.2f}ms (Weight: {best_model.weights_[i]:.1%})")

    # 5. Save the Model
    joblib.dump(best_model, model_filename)
    print(f"\n[+] Model successfully saved to: {model_filename}")
    
    # 6. Generate and save the plots
    plot_separated_models(best_model, results_df, str(output_dir), pcap_basename)