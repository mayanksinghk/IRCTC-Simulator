#!/bin/bash

# ==============================================================================
# IRCTC GMM Pipeline Deconvolution & Validation Batch Script
# ==============================================================================

# Create an output directory for the generated models and plots
OUTPUT_DIR="derived_models"
mkdir -p "$OUTPUT_DIR"

# 1. TOTAL MODELS (The delay including the target node)
# Edit these paths to point to your cumulative/total models.
declare -A TOTAL_MODELS
TOTAL_MODELS=(
    ["ips"]="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/PCAP/Code/3/3_model_mode1.pkl"
    ["adc"]="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/PCAP/Code/6-7/6-7_model_mode1.pkl"
    ["waf"]="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/PCAP/Code/8-9/8-9_model_mode2.pkl"
    ["web"]="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/PCAP/Code/10/10_model_mode2.pkl"
    ["fw2"]="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/PCAP/Code/11/11_model_mode2.pkl"
)

# 2. REST MODELS (The delay excluding the target node, or up to the previous hop)
# Edit these paths to point to the models you are subtracting.
declare -A REST_MODELS
REST_MODELS=(
    ["ips"]="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/PCAP/Code/5/5_model_mode1.pkl"
    ["adc"]="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/PCAP/Code/8-9/8-9_model_mode2.pkl" # Rest for ADC is everything up to IPS
    ["waf"]="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/PCAP/Code/10/10_model_mode2.pkl" # Rest for WAF is everything up to ADC
    ["web"]="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/PCAP/Code/11/11_model_mode2.pkl"
    ["fw2"]="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/PCAP/Code/12/12_model_mode2.pkl"
)

# Ordered list of nodes to process
NODES=("ips" "adc" "waf" "web" "fw2")

echo "============================================================"
echo " Starting Automated GMM Deconvolution Batch Job"
echo "============================================================"
echo "[*] All derived models and plots will be saved to: ./${OUTPUT_DIR}/"

for node in "${NODES[@]}"; do
    total_file="${TOTAL_MODELS[$node]}"
    rest_file="${REST_MODELS[$node]}"
    
    # Define outputs dynamically based on the node name
    output_model="${OUTPUT_DIR}/${node}_isolated_model.pkl"
    output_plot="${OUTPUT_DIR}/${node}_pipeline_validation.png"
    
    echo ""
    echo "[*] --------------------------------------------------------"
    echo "[*] Deriving Isolated Node: $(echo $node | tr '[:lower:]' '[:upper:]')"
    echo "[*] --------------------------------------------------------"

    # Safety Check: Does the Total model exist?
    if [[ ! -f "$total_file" ]]; then
        echo "[!] Error: Missing TOTAL model -> $total_file"
        echo "    Skipping $node..."
        continue
    fi

    # Safety Check: Does the Rest model exist?
    if [[ ! -f "$rest_file" ]]; then
        echo "[!] Error: Missing REST model -> $rest_file"
        echo "    Skipping $node..."
        continue
    fi

    # Execute the Python derivation and validation script
    python3 verify.py "$total_file" "$rest_file" "$output_model" "$output_plot"

done

echo ""
echo "============================================================"
echo " [+] Batch deconvolution complete! Check the '${OUTPUT_DIR}' folder."
echo "============================================================"