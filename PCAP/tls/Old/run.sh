#!/bin/bash

# ==================================================
#  CONFIGURATION
# ==================================================

# Input PCAPs
INPUTS=(
"./../../Data/Input_PCAP/3.pcap"
"./../../Data/Input_PCAP/5.pcap"
"./../../Data/Input_PCAP/6-7.pcap"
)

# Output directory base
OUT_BASE="."
mkdir -p "$OUT_BASE"

# Server subnets filter
TLS_FILTER='tls.record.content_type == 23 && (ip.addr==203.176.112.0/24 || ip.addr==203.176.113.0/24 || ip.addr==103.252.143.0/24 || ip.addr==103.252.142.0/24 || ip.addr==103.110.246.0/24)'

# Overwrite flag
OVERWRITE=0
if [[ "$1" == "--overwrite" ]]; then
    OVERWRITE=1
    echo "[!] Overwrite enabled: existing outputs will be replaced."
fi


# ==================================================
#  MAIN LOOP
# ==================================================
for INPUT_PCAP in "${INPUTS[@]}"; do

    NAME=$(basename "$INPUT_PCAP" .pcap)
    OUT_DIR="$OUT_BASE/$NAME"
    mkdir -p "$OUT_DIR"

    echo ""
    echo "==============================="
    echo "[*] Processing: $INPUT_PCAP"
    echo "[*] Output Dir: $OUT_DIR"
    echo "==============================="

    TLS_PCAP="$OUT_DIR/${NAME}_tls.pcap"
    RTT_CSV="$OUT_DIR/${NAME}_tls_rtt.csv"
    RTT_DIST_CSV="$OUT_DIR/${NAME}_rtt_distribution.csv"
    PNG_DIST="$OUT_DIR/${NAME}_tls_rtt_distribution.png"
    PNG_COUNTER="$OUT_DIR/${NAME}_tls_rtt_counter.png"


    # ==================================================
    # STEP 1 - Generate TLS filtered PCAP
    # ==================================================
    if [[ -f "$TLS_PCAP" && $OVERWRITE -eq 0 ]]; then
        echo "[✓] TLS PCAP already exists, skipping: $TLS_PCAP"
    else
        echo "[+] Running tshark TLS filter..."
        tshark -r "$INPUT_PCAP" \
            -Y "$TLS_FILTER" \
            -F pcap \
            -w "$TLS_PCAP" \
            -o "tls.desegment_ssl_records:TRUE" \
            -o "tls.desegment_ssl_application_data:TRUE"

        echo "[+] TLS filtered PCAP saved: $TLS_PCAP"
    fi


    # ==================================================
    # STEP 2 - Run tls_rtt.py to generate RTT CSV
    # ==================================================
    if [[ -f "$RTT_CSV" && $OVERWRITE -eq 0 ]]; then
        echo "[✓] RTT CSV already exists, skipping: $RTT_CSV"
    else
        echo "[+] Running tls_rtt.py..."
        python3 tls_rtt.py -i "$TLS_PCAP" -o "$RTT_CSV" -v
        echo "[+] RTT CSV saved: $RTT_CSV"
    fi


    # ==================================================
    # STEP 3 - Generate RTT distribution + graphs
    # ==================================================
    MAX_RTT=100000

    # Output files WITH max-RRT suffix
    RTT_DIST_OUT="${RTT_DIST_CSV}_${MAX_RTT}.csv"
    PNG_DIST_OUT="${PNG_DIST}_${MAX_RTT}.png"
    PNG_COUNTER_OUT="${PNG_COUNTER}_${MAX_RTT}.png"

    echo "[+] Running rtt.py for graphs + distribution (MAX_RTT=${MAX_RTT} ms)..."

    python3 rtt.py \
        -i "$RTT_CSV" \
        -o "$RTT_DIST_OUT" \
        --png_dist "$PNG_DIST_OUT" \
        --png_counter "$PNG_COUNTER_OUT" \
        --max_rtt "$MAX_RTT"

    echo "[+] Distribution CSV saved: $RTT_DIST_OUT"
    echo "[+] Graphs saved:"
    echo "    - $PNG_DIST_OUT"
    echo "    - $PNG_COUNTER_OUT"

    echo "-------------------------------------------"


done

echo ""
echo "==========================================="
echo "[✓] ALL PCAPS PROCESSED SUCCESSFULLY"
echo "==========================================="
