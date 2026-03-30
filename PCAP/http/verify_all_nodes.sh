#!/bin/bash

# --- CONFIGURATION ---
ISOLATED_DIR="./Mininet_Profiles"
TOTAL_DIR="./Analysis_Results"
VERIFY_OUT_DIR="./Verification_Results"
PYTHON_SCRIPT="./verify_convolution.py"

echo "=================================================="
echo " Starting Network Convolution Verification"
echo "=================================================="

# Create the output directory if it doesn't exist
mkdir -p "${VERIFY_OUT_DIR}"

# Helper function to check if a file exists
check_file() {
    if [ ! -f "$1" ]; then
        echo "[ERROR] Missing file required for verification: $1"
        exit 1
    fi
}

# --- Total Cumulative CSV Definitions ---
IPS_TOT="${TOTAL_DIR}/3_tls_delays.csv"
FRONT_FW_TOT="${TOTAL_DIR}/5_tls_delays.csv"
ADC_TOT="${TOTAL_DIR}/6-7_tls_delays.csv"
WAF_TOT="${TOTAL_DIR}/8-9_http_delays.csv"
WEB_TOT="${TOTAL_DIR}/10_http_delays.csv"
FW_TOT="${TOTAL_DIR}/11_http_delays.csv"
APP_TOT="${TOTAL_DIR}/12_http_delays.csv"


# --- 1. Verify IPS ---
echo -e "\n[1/5] Verifying IPS Convolution (Isolated (IPS + Front FW) + Downstream ADC == Original IPS+FW Total)"
IPS_ISO="${ISOLATED_DIR}/ips_Firewall_isolated.csv"

check_file "$IPS_ISO"
check_file "$FRONT_FW_TOT"
check_file "$IPS_TOT"

python3 "${PYTHON_SCRIPT}" \
    --isolated "${IPS_ISO}" \
    --downstream "${FRONT_FW_TOT}" \
    --original "${IPS_TOT}" \
    --outdir "${VERIFY_OUT_DIR}"
mv "${VERIFY_OUT_DIR}/convolution_verification.png" "${VERIFY_OUT_DIR}/verify_ips.png"


# --- 2. Verify ADC ---
echo -e "\n[2/5] Verifying ADC Convolution (Isolated ADC + Downstream WAF == Original ADC Total)"
ADC_ISO="${ISOLATED_DIR}/adc_isolated.csv"

check_file "$ADC_ISO"
check_file "$WAF_TOT"
check_file "$ADC_TOT"

python3 "${PYTHON_SCRIPT}" \
    --isolated "${ADC_ISO}" \
    --downstream "${WAF_TOT}" \
    --original "${ADC_TOT}" \
    --outdir "${VERIFY_OUT_DIR}"
mv "${VERIFY_OUT_DIR}/convolution_verification.png" "${VERIFY_OUT_DIR}/verify_adc.png"


# --- 3. Verify WAF ---
echo -e "\n[3/5] Verifying WAF Convolution (Isolated WAF + Downstream Web == Original WAF Total)"
WAF_ISO="${ISOLATED_DIR}/waf_isolated.csv"

check_file "$WAF_ISO"
check_file "$WEB_TOT"
check_file "$WAF_TOT"

python3 "${PYTHON_SCRIPT}" \
    --isolated "${WAF_ISO}" \
    --downstream "${WEB_TOT}" \
    --original "${WAF_TOT}" \
    --outdir "${VERIFY_OUT_DIR}"
mv "${VERIFY_OUT_DIR}/convolution_verification.png" "${VERIFY_OUT_DIR}/verify_waf.png"


# --- 4. Verify Web Server ---
echo -e "\n[4/5] Verifying Web Server Convolution (Isolated Web + Downstream FW == Original Web Total)"
WEB_ISO="${ISOLATED_DIR}/web_isolated.csv"

check_file "$WEB_ISO"
check_file "$FW_TOT"
check_file "$WEB_TOT"

python3 "${PYTHON_SCRIPT}" \
    --isolated "${WEB_ISO}" \
    --downstream "${FW_TOT}" \
    --original "${WEB_TOT}" \
    --outdir "${VERIFY_OUT_DIR}"
mv "${VERIFY_OUT_DIR}/convolution_verification.png" "${VERIFY_OUT_DIR}/verify_web.png"


# --- 5. Verify Firewall ---
echo -e "\n[5/5] Verifying Firewall Convolution (Isolated FW + Downstream App == Original FW Total)"
FW_ISO="${ISOLATED_DIR}/fw_isolated.csv"

check_file "$FW_ISO"
check_file "$APP_TOT"
check_file "$FW_TOT"

python3 "${PYTHON_SCRIPT}" \
    --isolated "${FW_ISO}" \
    --downstream "${APP_TOT}" \
    --original "${FW_TOT}" \
    --outdir "${VERIFY_OUT_DIR}"
mv "${VERIFY_OUT_DIR}/convolution_verification.png" "${VERIFY_OUT_DIR}/verify_fw.png"


echo -e "\n=================================================="
echo " SUCCESS: All verification tests completed!"
echo " Check the overlay graphs in: ${VERIFY_OUT_DIR}/"
echo "=================================================="