#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# ==============================================================================
# PORTABLE CONFIGURATION
# ==============================================================================
# Dynamically determine the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Define paths relative to the script's location
# full_gmm.py is in the PCAP/Code folder
PYTHON_SCRIPT="./full_gmm.py"

# PCAP directory is a sibling to 'Post_Simulation' inside the 'Mininet' folder
DATA_DIR="$SCRIPT_DIR/PCAP"

echo "============================================================"
echo " Starting IRCTC PCAP GMM Analysis Batch Job"
echo " Deleting old results "
echo "============================================================"
rm -rf server
# rm -rf ips
# rm -rf user1
# rm -rf waf1
# rm -rf web
# rm -rf fw2
# rm -rf app

echo "============================================================"
echo " Working Directory: $SCRIPT_DIR"
echo "============================================================"
# Function to run the python script and print verbose progress
run_analysis() {
    local pcap_file=$1
    local mode=$2
    local filename
    filename=$(basename "$pcap_file")
    
    echo -e "\n[$(date +'%Y-%m-%d %H:%M:%S')] ========================================"
    echo "[*] STARTING: $filename"
    echo "[*] MODE: $mode ($([ "$mode" -eq 1 ] && echo "TLS" || echo "HTTP"))"
    echo "[*] EXECUTING: python3 $PYTHON_SCRIPT $pcap_file $mode"
    echo "------------------------------------------------------------"
    
    # Check if file exists before running
    if [[ ! -f "$pcap_file" ]]; then
        echo "[!] ERROR: PCAP file not found -> $pcap_file"
        return 1
    fi

    # Run the actual Python command
    python3 "$PYTHON_SCRIPT" "$pcap_file" "$mode"
    
    echo "------------------------------------------------------------"
    echo "[+] SUCCESS: Finished processing $filename"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ========================================"
}

# # 1. Run TLS Modes (Mode 1)
# run_analysis "$DATA_DIR/adc1.pcap" 1
# run_analysis "$DATA_DIR/ips.pcap" 1
# run_analysis "$DATA_DIR/user1.pcap" 1

# 2. Run HTTP Modes (Mode 2)
run_analysis "$DATA_DIR/server.pcap" 2
# run_analysis "$DATA_DIR/waf1.pcap" 2
# run_analysis "$DATA_DIR/fw2.pcap" 2
# run_analysis "$DATA_DIR/web.pcap" 2
# run_analysis "$DATA_DIR/app.pcap" 2

echo -e "\n============================================================"
echo " ALL TASKS COMPLETED SUCCESSFULLY!"
echo "============================================================"