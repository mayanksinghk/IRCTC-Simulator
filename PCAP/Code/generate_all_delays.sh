#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# ==============================================================================
# GLOBAL CONFIGURATION & RELATIVE PATHS
# ==============================================================================
# Dynamically determine the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Python scripts are in the same folder as this bash script
PYTHON_SCRIPT="$SCRIPT_DIR/generate_mininet_delays.py"
ANALYZE_SCRIPT="$SCRIPT_DIR/analyze_node_math.py"

# Input Directory where models are stored is also this same folder
INPUT_DIR="$SCRIPT_DIR"

# Number of samples to generate for Mininet (default 100k)
SAMPLES=100000

# Output directory for the generated JSON files and Reports
OUT_DIR="mininet_delays"
mkdir -p "$OUT_DIR"

echo "============================================================"
echo " STARTING ENTERPRISE DELAY GENERATION & ANALYSIS"
echo " Working Directory: $SCRIPT_DIR"
echo "============================================================"

# Function for intermediate nodes (Calculates JSON and Math Report)
generate_intermediate() {
    local node_name=$1
    local total_model=$2
    local rest_model=$3
    local output_json="$OUT_DIR/${node_name}_delays.json"
    local output_report="$OUT_DIR/${node_name}_math_report.txt"
    
    echo -e "\n[*] Processing INTERMEDIATE Node: $node_name"
    
    # 1. Generate Mininet JSON
    python3 "$PYTHON_SCRIPT" \
        --total "$total_model" \
        --rest "$rest_model" \
        --samples "$SAMPLES" \
        --output "$output_json"
        
    # 2. Run Analytical Math Analysis
    python3 "$ANALYZE_SCRIPT" \
        --total "$total_model" \
        --rest "$rest_model" \
        --save "$output_report"
}

# Function for terminal nodes (Calculates JSON and Math Report)
generate_terminal() {
    local node_name=$1
    local target_model=$2
    local output_json="$OUT_DIR/${node_name}_delays.json"
    local output_report="$OUT_DIR/${node_name}_math_report.txt"
    
    echo -e "\n[*] Processing TERMINAL Node: $node_name"
    
    # 1. Generate Mininet JSON
    python3 "$PYTHON_SCRIPT" \
        --total "$target_model" \
        --samples "$SAMPLES" \
        --output "$output_json"
        
    # 2. Run Analytical Math Analysis
    python3 "$ANALYZE_SCRIPT" \
        --total "$target_model" \
        --save "$output_report"
}

# ============================================================
# 1. IPS (Intrusion Prevention System)
# ============================================================
generate_intermediate "ips" "$INPUT_DIR/3/3_model_mode1.pkl" "$INPUT_DIR/5/5_model_mode1.pkl"

# ============================================================
# 2. ADC (Application Delivery Controller)
# ============================================================
generate_intermediate "adc" "$INPUT_DIR/6-7/6-7_model_mode1.pkl" "$INPUT_DIR/8-9/8-9_model_mode2.pkl"

# ============================================================
# 3. WAF (Web Application Firewall)
# ============================================================
generate_intermediate "waf" "$INPUT_DIR/8-9/8-9_model_mode2.pkl" "$INPUT_DIR/10/10_model_mode2.pkl"

# ============================================================
# 4. WEB SERVER
# ============================================================
generate_intermediate "web_server" "$INPUT_DIR/10/10_model_mode2.pkl" "$INPUT_DIR/11/11_model_mode2.pkl"

# ============================================================
# 5. ACTIVE BACKEND FIREWALL
# ============================================================
generate_intermediate "backend_firewall" "$INPUT_DIR/11/11_model_mode2.pkl" "$INPUT_DIR/12/12_model_mode2.pkl"

# ============================================================
# 6. APPLICATION SERVER (Terminal Node)
# ============================================================ 
generate_terminal "application_server" "$INPUT_DIR/12/12_model_mode2.pkl"


echo -e "\n============================================================"
echo " ALL DELAYS GENERATED & ANALYZED SUCCESSFULLY!"
echo " Mininet JSONs + Math Reports: ./${OUT_DIR}/"
echo "============================================================"

echo -e "\n[*] Do you want to copy the ${OUT_DIR} contents to the Mininet VM? (y/n)"
read -r REPLY

if [[ "$REPLY" =~ ^[Yy]$ ]]; then
    # Calculate the destination path relative to the script's directory
    # Moves up from PCAP/Code to PCAP/ then up to Root/ then into Mininet/
    DEST_DIR="$SCRIPT_DIR/../../Mininet"
    
    if [ -d "$DEST_DIR" ]; then
        # Perform the copy
        cp -r "$OUT_DIR" "$DEST_DIR/"
        
        # Resolve the absolute path for the final success message
        ABS_DEST=$(cd "$DEST_DIR" 2>/dev/null && pwd)
        echo "[+] Files copied successfully to: $ABS_DEST/$OUT_DIR"
    else
        echo "[!] Error: Destination directory not found at $DEST_DIR"
    fi
else
    echo "Skipping file transfer. You can manually copy the ${OUT_DIR} directory to your Mininet VM."
fi