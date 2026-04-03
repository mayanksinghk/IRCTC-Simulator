#!/usr/bin/env python3
import argparse
import joblib
import numpy as np
import os
import sys

def calculate_gmm_overall_stats(gmm):
    """
    Calculates the aggregate Mean and Variance of a GMM based on its components.
    """
    weights = gmm.weights_
    means = gmm.means_.flatten()
    variances = gmm.covariances_.flatten()
    
    # 1. Overall Mean: sum(weight * mean)
    overall_mean = np.sum(weights * means)
    
    # 2. Overall Variance: E[X^2] - (E[X])^2
    expected_x_squared = np.sum(weights * (variances + means**2))
    overall_variance = expected_x_squared - (overall_mean**2)
    
    return overall_mean, overall_variance

def analyze_isolated_node(total_path, rest_path, save_path):
    if not os.path.exists(total_path):
        print(f"[X] Error: Target model '{total_path}' not found.")
        return

    total_gmm = joblib.load(total_path)
    mu_T, var_T = calculate_gmm_overall_stats(total_gmm)

    if rest_path and rest_path.upper() != "NONE":
        if not os.path.exists(rest_path):
            print(f"[X] Error: Rest model '{rest_path}' not found.")
            return
            
        rest_gmm = joblib.load(rest_path)
        mu_R, var_R = calculate_gmm_overall_stats(rest_gmm)
        mu_N = mu_T - mu_R
        var_N = var_T - var_R
        mode_label = "INTERMEDIATE (T - R)"
    else:
        mu_N = mu_T
        var_N = var_T
        mu_R, var_R = 0, 0
        mode_label = "TERMINAL (Target Only)"

    # --- BUILD THE REPORT STRING ---
    report = []
    report.append("="*55)
    report.append(f" ANALYTICAL NODE REPORT: {mode_label}")
    report.append("="*55)
    report.append(f"Source Total: {os.path.basename(total_path)}")
    if mu_R > 0:
        report.append(f"Source Rest:  {os.path.basename(rest_path)}")
    report.append("-" * 55)
    
    report.append(f"[1] TOTAL OBSERVED (T)")
    report.append(f"    Mean:     {mu_T * 1000:8.2f} ms")
    report.append(f"    Std Dev:  {np.sqrt(var_T) * 1000:8.2f} ms\n")
    
    if mu_R > 0:
        report.append(f"[2] REST OF NETWORK (R)")
        report.append(f"    Mean:     {mu_R * 1000:8.2f} ms")
        report.append(f"    Std Dev:  {np.sqrt(var_R) * 1000:8.2f} ms\n")
    
    report.append("-" * 55)
    report.append(f"[3] ISOLATED NODE RESULT (N)")
    
    if mu_N < 0:
        report.append(f"    [!] WARNING: Negative Mean ({mu_N * 1000:.2f}ms).")
    else:
        report.append(f"    Mean:     {mu_N * 1000:8.2f} ms")
        
    if var_N < 0:
        report.append(f"    [!] WARNING: Negative Variance. Models incompatible.")
    else:
        report.append(f"    Std Dev:  {np.sqrt(var_N) * 1000:8.2f} ms")
    report.append("="*55 + "\n")

    final_output = "\n".join(report)

    # --- OUTPUT LOGIC ---
    if save_path:
        with open(save_path, 'w') as f:
            f.write(final_output)
        print(f"[+] Analytical report saved to: {save_path}")
    else:
        print(final_output)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Analytical GMM Node Subtraction with File Output.")
    parser.add_argument("--total", required=True, help="Path to Total Network GMM (.pkl)")
    parser.add_argument("--rest", required=False, default=None, help="Path to Rest GMM or 'NONE'")
    parser.add_argument("--save", required=False, default=None, help="Optional: Filename to save the report")
    
    args = parser.parse_args()
    analyze_isolated_node(args.total, args.rest, args.save)