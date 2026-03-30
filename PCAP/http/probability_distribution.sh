#!/bin/bash

# --- CONFIGURATION ---
PCAP_DIR="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/Data/Input_PCAP"
OUTPUT_BASE_DIR="./Analysis_Results"

# Python Scripts
HTTP_PYTHON_SCRIPT="./probability_distribution.py"
TLS_PYTHON_SCRIPT="./tls_probability_distribution.py" # Ensure this matches your actual filename

# Array for standard HTTP PCAPs
HTTP_PCAP_FILES=(
    "8-9.pcap"
    "10.pcap"
    "11.pcap"
    "12.pcap"
)

# Array for Encrypted TLS PCAPs
TLS_PCAP_FILES=(
    "3.pcap"
    "5.pcap"
    "6-7.pcap"
)

echo "=================================================="
echo " Starting Parallel PCAP Analysis (HTTP & TLS)"
echo "=================================================="

# Create the output directory if it doesn't exist
mkdir -p "${OUTPUT_BASE_DIR}"

# --------------------------------------------------
# 1. Launch HTTP Jobs
# --------------------------------------------------
echo ">>> Launching HTTP Analysis Jobs..."
for pcap in "${HTTP_PCAP_FILES[@]}"; do
    INPUT_PATH="${PCAP_DIR}/${pcap}"
    BASENAME="${pcap%.pcap}"
    
    if [ ! -f "${INPUT_PATH}" ]; then
        echo "[WARNING] HTTP File not found: ${INPUT_PATH}"
        continue
    fi

    echo " -> [HTTP] Background job for: ${pcap}"
    
    python3 "${HTTP_PYTHON_SCRIPT}" \
        -i "${INPUT_PATH}" \
        -o "${OUTPUT_BASE_DIR}" \
        --csv_name "${BASENAME}_http_delays.csv" \
        --graph_name "${BASENAME}_http_distribution.png" &
done

# --------------------------------------------------
# 2. Launch TLS Jobs
# --------------------------------------------------
echo ">>> Launching TLS Analysis Jobs..."
for pcap in "${TLS_PCAP_FILES[@]}"; do
    INPUT_PATH="${PCAP_DIR}/${pcap}"
    BASENAME="${pcap%.pcap}"
    
    if [ ! -f "${INPUT_PATH}" ]; then
        echo "[WARNING] TLS File not found: ${INPUT_PATH}"
        continue
    fi

    echo " -> [TLS] Background job for: ${pcap}"
    
    # Executes the new high-speed dpkt script
    python3 "${TLS_PYTHON_SCRIPT}" \
        -i "${INPUT_PATH}" \
        -o "${OUTPUT_BASE_DIR}" \
        --csv_name "${BASENAME}_tls_delays.csv" \
        --graph_name "${BASENAME}_tls_distribution.png" &
done

echo "--------------------------------------------------"
echo " All jobs launched. Waiting for them to finish..."
echo "--------------------------------------------------"

# The 'wait' command blocks the script from exiting until all background '&' jobs complete
wait

echo "=================================================="
echo " SUCCESS: All parallel analysis jobs completed!"
echo " Results are saved in: ${OUTPUT_BASE_DIR}"
echo "=================================================="