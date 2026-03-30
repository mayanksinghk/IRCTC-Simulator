#!/bin/bash

# --- CONFIGURATION ---
# Where your cumulative CSV files from the previous step are stored
INPUT_DIR="./Analysis_Results"

# Where you want to save the final isolated Mininet profiles
OUTPUT_DIR="./Mininet_Profiles"

# Path to the python script
PYTHON_SCRIPT="./calculate_node_deltas.py"

# Define your input CSV files (Update these names to match exactly what you generated)
IPS_CSV="${INPUT_DIR}/3_tls_delays.csv"  
Front_FW_CSV="${INPUT_DIR}/5_tls_delays.csv"  
ADC_CSV="${INPUT_DIR}/6-7_tls_delays.csv"
WAF_CSV="${INPUT_DIR}/8-9_http_delays.csv"
WEB_CSV="${INPUT_DIR}/10_http_delays.csv"
FW_CSV="${INPUT_DIR}/11_http_delays.csv"
APP_CSV="${INPUT_DIR}/12_http_delays.csv"

# ---------------------------------------------------------

echo "=================================================="
echo " Starting Isolated Node Delay Calculation"
echo "=================================================="

# Create the output directory if it doesn't exist
mkdir -p "${OUTPUT_DIR}"

# Helper function to check if files exist before running Python
check_file() {
    if [ ! -f "$1" ]; then
        echo "[ERROR] Could not find file: $1"
        echo "Please check your INPUT_DIR and file names."
        exit 1
    fi
}

# Verify all input files exist
check_file "${IPS_CSV}"
check_file "${Front_FW_CSV}"
check_file "${ADC_CSV}"
check_file "${WAF_CSV}"
check_file "${WEB_CSV}"
check_file "${FW_CSV}"
check_file "${APP_CSV}"

# --- 1. Isolate IPS+FW Firewall Delay (Active Perimeter IPS Total - Front FW Total) ---
echo -e "\n[1/5] Calculating Active Perimeter IPS Isolated Delay..."
python3 "${PYTHON_SCRIPT}" \
    --upstream "${IPS_CSV}" \
    --downstream "${Front_FW_CSV}" \
    --out "${OUTPUT_DIR}/ips_Firewall_isolated.csv"

# --- 2. Isolate ADC Delay (Front FW Total - ADC Total) ---
echo -e "\n[1/5] Calculating Active Front End Firewall Isolated Delay..."
python3 "${PYTHON_SCRIPT}" \
    --upstream "${ADC_CSV}" \
    --downstream "${WAF_CSV}" \
    --out "${OUTPUT_DIR}/adc_isolated.csv"

# --- 3. Isolate WAF Delay (WAF Total - Web Server Total) ---
echo -e "\n[2/5] Calculating WAF Isolated Delay..."
python3 "${PYTHON_SCRIPT}" \
    --upstream "${WAF_CSV}" \
    --downstream "${WEB_CSV}" \
    --out "${OUTPUT_DIR}/waf_isolated.csv"

# --- 4. Isolate Web Server Delay (Web Total - Firewall Total) ---
echo -e "\n[3/5] Calculating Web Server Isolated Delay..."
python3 "${PYTHON_SCRIPT}" \
    --upstream "${WEB_CSV}" \
    --downstream "${FW_CSV}" \
    --out "${OUTPUT_DIR}/web_isolated.csv"

# --- 5. Isolate Firewall Delay (Firewall Total - App Server Total) ---
echo -e "\n[4/5] Calculating Firewall Isolated Delay..."
python3 "${PYTHON_SCRIPT}" \
    --upstream "${FW_CSV}" \
    --downstream "${APP_CSV}" \
    --out "${OUTPUT_DIR}/fw_isolated.csv"

# --- 6. App Server (End of the line, no subtraction needed) ---
echo -e "\n[5/5] Processing App Server Delay..."
echo "Copying ${APP_CSV} directly to profiles (App Server is the final destination)."
cp "${APP_CSV}" "${OUTPUT_DIR}/app_isolated.csv"

echo -e "\n=================================================="
echo " SUCCESS: All isolated profiles generated!"
echo " You can find them in: ${OUTPUT_DIR}/"
echo "=================================================="