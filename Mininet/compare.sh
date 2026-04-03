#!/bin/bash

# ==============================================================================
# IRCTC GMM Digital Twin Comparison Batch Script (Portable Version)
# ==============================================================================

# Dynamically determine the directory where this script is located (Mininet folder)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Define base paths relative to this script 
# PCAP/Code is a sibling to the Mininet folder
BASELINE_BASE="$SCRIPT_DIR/../PCAP/Code" 
# Post_Simulation is inside the Mininet folder
EMULATED_BASE="$SCRIPT_DIR/Post_Simulation" 

# Define the paths to your Original Baseline models
declare -A BASELINES
BASELINES=(
    ["ips"]="$BASELINE_BASE/3/3_model_mode1.pkl"
    ["adc"]="$BASELINE_BASE/6-7/6-7_model_mode1.pkl"
    ["waf"]="$BASELINE_BASE/8-9/8-9_model_mode2.pkl"
    ["web"]="$BASELINE_BASE/10/10_model_mode2.pkl"
    ["fw2"]="$BASELINE_BASE/11/11_model_mode2.pkl"
    ["app"]="$BASELINE_BASE/12/12_model_mode2.pkl"
)

# Define the paths to your Emulated models [cite: 36, 37, 38]
declare -A EMULATED
EMULATED=(
    ["ips"]="$EMULATED_BASE/ips/ips_model_mode1.pkl"
    ["adc"]="$EMULATED_BASE/adc1/adc1_model_mode1.pkl"
    ["waf"]="$EMULATED_BASE/waf1/waf1_model_mode2.pkl"
    ["web"]="$EMULATED_BASE/web/web_model_mode2.pkl"
    ["fw2"]="$EMULATED_BASE/fw2/fw2_model_mode2.pkl"
    ["app"]="$EMULATED_BASE/app/app_model_mode2.pkl"
)

# Ordered list of nodes for a logical pipeline output
NODES=("ips" "adc" "waf" "web" "fw2" "app")

echo "============================================================"
echo " Starting Automated GMM Comparison Batch Job"
echo "============================================================"

for node in "${NODES[@]}"; do
    baseline_file="${BASELINES[$node]}"
    emulated_file="${EMULATED[$node]}"
    
    echo ""
    echo "[*] --------------------------------------------------------"
    echo "[*] Analyzing Node: $(echo $node | tr '[:lower:]' '[:upper:]')"
    echo "[*] --------------------------------------------------------"

    # Check if baseline model exists
    if [[ ! -f "$baseline_file" ]]; then
        echo "[!] Error: Missing baseline model -> $baseline_file"
        continue
    fi

    # Check if emulated model exists
    if [[ ! -f "$emulated_file" ]]; then
        echo "[!] Error: Missing emulated model -> $emulated_file"
        continue
    fi

    # Execute the Python comparison script using its local path
    python3 "$SCRIPT_DIR/compare_gmm.py" "$baseline_file" "$emulated_file"

done

echo ""
echo "============================================================"
echo " [+] Batch comparison complete!"
echo "============================================================"