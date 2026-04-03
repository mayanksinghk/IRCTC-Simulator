#!/bin/bash

# ==============================================================================
# IRCTC GMM Pipeline Deconvolution & Validation Batch Script (Relative Paths)
# ==============================================================================

# Dynamically determine the directory where THIS script is located
# This allows the script to resolve paths regardless of where it is run from
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Path to the Python verification logic (lives in the same directory)
VERIFY_PY="$SCRIPT_DIR/verify.py"

# Create an output directory for the generated models and plots
OUTPUT_DIR="derived_models"
mkdir -p "$OUTPUT_DIR"

# 1. TOTAL MODELS (The delay including the target node)
# Uses $SCRIPT_DIR to point to the subfolders in your IRCTC-Simulator 
declare -A TOTAL_MODELS
TOTAL_MODELS=(
    ["ips"]="$SCRIPT_DIR/3/3_model_mode1.pkl"
    ["adc"]="$SCRIPT_DIR/6-7/6-7_model_mode1.pkl"
    ["waf"]="$SCRIPT_DIR/8-9/8-9_model_mode2.pkl"
    ["web"]="$SCRIPT_DIR/10/10_model_mode2.pkl"
    ["fw2"]="$SCRIPT_DIR/11/11_model_mode2.pkl"
)

# 2. REST MODELS (The delay excluding the target node)
declare -A REST_MODELS
REST_MODELS=(
    ["ips"]="$SCRIPT_DIR/5/5_model_mode1.pkl"
    ["adc"]="$SCRIPT_DIR/8-9/8-9_model_mode2.pkl"
    ["waf"]="$SCRIPT_DIR/10/10_model_mode2.pkl"
    ["web"]="$SCRIPT_DIR/11/11_model_mode2.pkl"
    ["fw2"]="$SCRIPT_DIR/12/12_model_mode2.pkl"
)

# Ordered list of nodes to process
NODES=("ips" "adc" "waf" "web" "fw2")

echo "============================================================"
echo " Starting Automated GMM Deconvolution Batch Job"
echo " Base Path: $SCRIPT_DIR"
echo "============================================================"
echo "[*] All derived models and plots will be saved to: ./${OUTPUT_DIR}/"

# Verify Python script existence before starting
if [[ ! -f "$VERIFY_PY" ]]; then
    echo "[!] Error: verify.py not found at $VERIFY_PY"
    exit 1
fi

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

    # Execute the Python derivation and validation script using its absolute-relative path
    python3 "$VERIFY_PY" "$total_file" "$rest_file" "$output_model" "$output_plot"

done

echo ""
echo "============================================================"
echo " [+] Batch deconvolution complete! Check the '${OUTPUT_DIR}' folder."
echo "============================================================"