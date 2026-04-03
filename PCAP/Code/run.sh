#!/bin/bash

# Exit immediately if a command exits with a non-zero status
set -e

# Define variables for cleaner code
PYTHON_SCRIPT="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/PCAP/Code/full_gmm.py"
DATA_DIR="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/Data/Input_PCAP"

echo "============================================================"
echo " Starting IRCTC PCAP GMM Analysis Batch Job"
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
    
    # Run the actual Python command
    python3 "$PYTHON_SCRIPT" "$pcap_file" "$mode"
    
    echo "------------------------------------------------------------"
    echo "[+] SUCCESS: Finished processing $filename"
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ========================================"
}

# 1. Run TLS Modes (Mode 1)
run_analysis "$DATA_DIR/3.pcap" 1
run_analysis "$DATA_DIR/5.pcap" 1
run_analysis "$DATA_DIR/6-7.pcap" 1

# 2. Run HTTP Modes (Mode 2)
run_analysis "$DATA_DIR/8-9.pcap" 2
run_analysis "$DATA_DIR/10.pcap" 2
run_analysis "$DATA_DIR/11.pcap" 2
run_analysis "$DATA_DIR/12.pcap" 2

echo -e "\n============================================================"
echo " ALL TASKS COMPLETED SUCCESSFULLY!"
echo "============================================================"