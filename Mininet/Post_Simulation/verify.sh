#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# ==============================================================================
# GLOBAL CONFIGURATION & RELATIVE PATHS
# ==============================================================================
# Dynamically determine the directory where this script is located
SCRIPT_DIR1="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_DIR="$SCRIPT_DIR1/../../PCAP/Code"

# Python scripts are in the same folder as this bash script
PYTHON_SCRIPT="$SCRIPT_DIR1/difference_gmm.py"

# Input Directory where models are stored is also this same folder
INPUT_DIR="$SCRIPT_DIR1"
# SCRIPT_DIR="$SCRIPT_DIR/../../PCAP/Code"

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
    python3 "$PYTHON_SCRIPT" "$total_model" "$rest_model" 
        
}


# ============================================================
# 1. IPS (Intrusion Prevention System)
# ============================================================
generate_intermediate "ips" "$INPUT_DIR/ips/ips_model_mode1.pkl" "$SCRIPT_DIR/3/3_model_mode1.pkl"

# ============================================================
# 2. ADC (Application Delivery Controller)
# ============================================================
generate_intermediate "adc" "$INPUT_DIR/adc1/adc1_model_mode1.pkl" "$SCRIPT_DIR/6-7/6-7_model_mode1.pkl"

# ============================================================
# 3. WAF (Web Application Firewall)
# ============================================================
generate_intermediate "waf" "$INPUT_DIR/waf1/waf1_model_mode2.pkl" "$SCRIPT_DIR/8-9/8-9_model_mode2.pkl"

# ============================================================
# 4. WEB SERVER
# ============================================================
generate_intermediate "web_server" "$INPUT_DIR/web/web_model_mode2.pkl" "$SCRIPT_DIR/11/11_model_mode2.pkl"

# ============================================================
# 5. ACTIVE BACKEND FIREWALL
# ============================================================
generate_intermediate "backend_firewall" "$INPUT_DIR/fw2/fw2_model_mode2.pkl" "$SCRIPT_DIR/11/11_model_mode2.pkl"

# ============================================================
# 6. APPLICATION SERVER (Terminal Node)
# ============================================================ 
generate_intermediate "application_server" "$INPUT_DIR/app/app_model_mode2.pkl" "$SCRIPT_DIR/12/12_model_mode2.pkl"


echo -e "\n============================================================"
echo " ALL DELAYS GENERATED & ANALYZED SUCCESSFULLY!"
echo " Mininet JSONs + Math Reports: ./${OUT_DIR}/"
echo "============================================================"