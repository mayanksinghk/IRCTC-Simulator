#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# ==============================================================================
# GLOBAL CONFIGURATION & RELATIVE PATHS
# ==============================================================================
# Dynamically determine the directory where this script is located
# This allows the script to resolve internal paths regardless of where it is run from [cite: 8]
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Define paths relative to the script's location (PCAP/Code) [cite: 8, 40]
PCAP_DATA_DIR="$SCRIPT_DIR/../../Data/Input_PCAP"
CODE_DIR="$SCRIPT_DIR"

# Python Scripts located in PCAP/Code [cite: 42, 43]
FULL_GMM_SCRIPT="$CODE_DIR/full_gmm.py"
VERIFY_SCRIPT="$CODE_DIR/verify.py"
GENERATE_SCRIPT="$CODE_DIR/generate_mininet_delays.py"
ANALYZE_SCRIPT="$CODE_DIR/analyze_node_math.py"

# Output Directories (Created in the current working directory)
DERIVED_DIR="derived_models"
DELAYS_DIR="mininet_delays"
SAMPLES=100000

# Create necessary output directories
mkdir -p "$DERIVED_DIR"
mkdir -p "$DELAYS_DIR"

echo "============================================================"
echo " STAGE 1: IRCTC PCAP GMM Analysis (Generating Baseline Models)"
echo "============================================================"

run_analysis() {
    local pcap_file=$1
    local mode=$2
    local filename
    filename=$(basename "$pcap_file")
    
    echo -e "\n[$(date +'%Y-%m-%d %H:%M:%S')] ========================================"
    echo "[*] STARTING: $filename"
    echo "[*] MODE: $mode ($([ "$mode" -eq 1 ] && echo "TLS" || echo "HTTP"))"
    echo "[*] EXECUTING: python3 $FULL_GMM_SCRIPT $pcap_file $mode"
    echo "------------------------------------------------------------"
    
    python3 "$FULL_GMM_SCRIPT" "$pcap_file" "$mode"
    
    echo "------------------------------------------------------------"
    echo "[+] SUCCESS: Finished processing $filename"
}

# Process TLS Modes (Mode 1) [cite: 11, 41]
run_analysis "$PCAP_DATA_DIR/3.pcap" 1
run_analysis "$PCAP_DATA_DIR/5.pcap" 1
run_analysis "$PCAP_DATA_DIR/6-7.pcap" 1

# Process HTTP Modes (Mode 2) [cite: 8, 40, 41]
run_analysis "$PCAP_DATA_DIR/8-9.pcap" 2
run_analysis "$PCAP_DATA_DIR/10.pcap" 2
run_analysis "$PCAP_DATA_DIR/11.pcap" 2
run_analysis "$PCAP_DATA_DIR/12.pcap" 2

echo -e "\n============================================================"
echo " STAGE 2: Pipeline Deconvolution & Validation (Isolating Nodes)"
echo "============================================================"
echo "[*] Derived models and plots will be saved to: ./${DERIVED_DIR}/"

# Maps Cumulative Models (Total Delay including the target node) [cite: 40, 41, 42]
declare -A TOTAL_MODELS=(
    ["ips"]="$CODE_DIR/3/3_model_mode1.pkl"
    ["adc"]="$CODE_DIR/6-7/6-7_model_mode1.pkl"
    ["waf"]="$CODE_DIR/8-9/8-9_model_mode2.pkl"
    ["web"]="$CODE_DIR/10/10_model_mode2.pkl"
    ["fw2"]="$CODE_DIR/11/11_model_mode2.pkl"
)

# Maps Baseline Models (Delay excluding the target node/previous hop) [cite: 41, 42]
declare -A REST_MODELS=(
    ["ips"]="$CODE_DIR/5/5_model_mode1.pkl"
    ["adc"]="$CODE_DIR/8-9/8-9_model_mode2.pkl"
    ["waf"]="$CODE_DIR/10/10_model_mode2.pkl"
    ["web"]="$CODE_DIR/11/11_model_mode2.pkl"
    ["fw2"]="$CODE_DIR/12/12_model_mode2.pkl"
)

NODES=("ips" "adc" "waf" "web" "fw2")

for node in "${NODES[@]}"; do
    total_file="${TOTAL_MODELS[$node]}"
    rest_file="${REST_MODELS[$node]}"
    output_model="${DERIVED_DIR}/${node}_isolated_model.pkl"
    output_plot="${DERIVED_DIR}/${node}_pipeline_validation.png"
    
    echo -e "\n[*] Deriving Isolated Node: $(echo "$node" | tr '[:lower:]' '[:upper:]')"
    
    if [[ ! -f "$total_file" ]] || [[ ! -f "$rest_file" ]]; then
        echo "[!] Error: Missing required pkl models for $node. Skipping..."
        continue
    fi

    python3 "$VERIFY_SCRIPT" "$total_file" "$rest_file" "$output_model" "$output_plot"
done

echo -e "\n============================================================"
echo " STAGE 3: Enterprise Delay Generation for Mininet"
echo "============================================================"

generate_intermediate() {
    local node_name=$1
    local total_model=$2
    local rest_model=$3
    local output_json="$DELAYS_DIR/${node_name}_delays.json"
    local output_report="$DELAYS_DIR/${node_name}_math_report.txt"
    
    echo -e "\n[*] Processing INTERMEDIATE Node: $node_name"
    python3 "$GENERATE_SCRIPT" --total "$total_model" --rest "$rest_model" --samples "$SAMPLES" --output "$output_json"
    python3 "$ANALYZE_SCRIPT" --total "$total_model" --rest "$rest_model" --save "$output_report"
}

generate_terminal() {
    local node_name=$1
    local target_model=$2
    local output_json="$DELAYS_DIR/${node_name}_delays.json"
    local output_report="$DELAYS_DIR/${node_name}_math_report.txt"
    
    echo -e "\n[*] Processing TERMINAL Node: $node_name"
    python3 "$GENERATE_SCRIPT" --total "$target_model" --samples "$SAMPLES" --output "$output_json"
    python3 "$ANALYZE_SCRIPT" --total "$target_model" --save "$output_report"
}

# Generate Delays based on model hierarchy [cite: 40, 41, 42]
generate_intermediate "ips" "$CODE_DIR/3/3_model_mode1.pkl" "$CODE_DIR/5/5_model_mode1.pkl"
generate_intermediate "adc" "$CODE_DIR/6-7/6-7_model_mode1.pkl" "$CODE_DIR/8-9/8-9_model_mode2.pkl"
generate_intermediate "waf" "$CODE_DIR/8-9/8-9_model_mode2.pkl" "$CODE_DIR/10/10_model_mode2.pkl"
generate_intermediate "web_server" "$CODE_DIR/10/10_model_mode2.pkl" "$CODE_DIR/11/11_model_mode2.pkl"
generate_intermediate "backend_firewall" "$CODE_DIR/11/11_model_mode2.pkl" "$CODE_DIR/12/12_model_mode2.pkl"
generate_terminal "application_server" "$CODE_DIR/12/12_model_mode2.pkl"

echo -e "\n============================================================"
echo " ALL PIPELINE TASKS COMPLETED SUCCESSFULLY!"
echo " Results stored in local directories: ${DERIVED_DIR} and ${DELAYS_DIR}"
echo "============================================================"

# ==============================================================================
# POST-EXECUTION FILE TRANSFER
# ==============================================================================
echo -e "\n[*] Do you want to copy the ${DELAYS_DIR} contents to the Mininet folder? (y/n)"
read -r REPLY

if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    # Calculate absolute destination path relative to script folder [cite: 35]
    DEST_DIR="$SCRIPT_DIR/../../Mininet"
    
    if [ -d "$DEST_DIR" ]; then
        cp -r "$DELAYS_DIR" "$DEST_DIR/"
        ABS_DEST=$(cd "$DEST_DIR" 2>/dev/null && pwd)
        FINAL_PATH="${ABS_DEST}/${DELAYS_DIR}"
        echo "[+] Files copied successfully to: $FINAL_PATH"
    else
        echo "[!] Error: Destination directory not found at $DEST_DIR"
    fi
else
    echo "Skipping file transfer. You can manually copy the ${DELAYS_DIR} directory."
fi