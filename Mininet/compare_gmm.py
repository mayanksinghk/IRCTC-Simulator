#!/usr/bin/env python3
import sys
import numpy as np
from sklearn.mixture import GaussianMixture
import joblib

def calculate_kl_divergence(gmm_p, gmm_q, n_samples=100000):
    """
    Approximates the Kullback-Leibler divergence D_KL(P || Q) between two GMMs
    using Monte Carlo sampling.
    """
    # 1. Sample data points from the 'true' distribution (Model P)
    samples_p, _ = gmm_p.sample(n_samples)
    
    # 2. Calculate the log-likelihood of these samples under Model P
    log_prob_p = gmm_p.score_samples(samples_p)
    
    # 3. Calculate the log-likelihood of these same samples under Model Q
    log_prob_q = gmm_q.score_samples(samples_p)
    
    # 4. The KL divergence is the expected value of the difference
    kl_divergence = np.mean(log_prob_p - log_prob_q)
    
    return max(0.0, kl_divergence)

def calculate_symmetric_divergence(gmm_p, gmm_q, n_samples=100000):
    """
    Calculates a symmetric version of KL divergence.
    """
    kl_p_q = calculate_kl_divergence(gmm_p, gmm_q, n_samples)
    kl_q_p = calculate_kl_divergence(gmm_q, gmm_p, n_samples)
    
    return (kl_p_q + kl_q_p) / 2.0

if __name__ == "__main__":
    # Handle Command Line Arguments
    if len(sys.argv) < 3:
        print("Usage: python3 compare_gmm.py <baseline_model.pkl> <emulated_model.pkl>")
        sys.exit(1)

    BASELINE_PATH = sys.argv[1]
    EMULATED_PATH = sys.argv[2]

    try:
        print(f"[*] Loading Baseline Model: {BASELINE_PATH}")
        baseline_gmm = joblib.load(BASELINE_PATH)
        
        print(f"[*] Loading Emulated Model: {EMULATED_PATH}")
        emulated_gmm = joblib.load(EMULATED_PATH)
        
        print("[*] Running Monte Carlo Integration (100,000 samples)...")
        kl_score = calculate_kl_divergence(baseline_gmm, emulated_gmm)
        sym_score = calculate_symmetric_divergence(baseline_gmm, emulated_gmm)
        
        print("\n" + "="*55)
        print("          GMM MATHEMATICAL COMPARISON RESULTS")
        print("="*55)
        print(f" Baseline: {BASELINE_PATH}")
        print(f" Emulated: {EMULATED_PATH}")
        print("-" * 55)
        print(f" KL Divergence (Baseline || Emulated): {kl_score:.4f} nats")
        print(f" Symmetric Distance Score:             {sym_score:.4f} nats")
        print("-" * 55)
        
        # Interpretation Guide
        if sym_score < 0.1:
            print("[+] Conclusion: Excellent match. The emulation is mathematically nearly identical.")
        elif sym_score < 0.5:
            print("[~] Conclusion: Good match. The emulation captures the main components well.")
        elif sym_score < 1.0:
            print("[!] Conclusion: Fair match. There is noticeable structural drift in the peaks.")
        else:
            print("[-] Conclusion: Poor match. The emulation distribution is fundamentally different.")
            
    except FileNotFoundError as e:
        print(f"\n[!] Error: Could not find the model file. Did you provide the correct path?\n{e}")
    except Exception as e:
        print(f"\n[!] An unexpected error occurred: {e}")