#!/bin/bash

# ==================================================
#  CONFIGURATION
# ==================================================

# Input PCAPs
INPUTS=(
"./../../Data/Input_PCAP/8-9.pcap"
"./../../Data/Input_PCAP/10.pcap"
"./../../Data/Input_PCAP/11.pcap"
"./../../Data/Input_PCAP/12.pcap"
)

# Output directory base
OUT_BASE="."
mkdir -p "$OUT_BASE"

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

    # ==================================================
    # STEP 1 - Run http_rtt.py to generate RTT CSV
    # ==================================================
    RTT_CSV="$OUT_DIR/${NAME}_http_rtt.csv"
    if [[ -f "$RTT_CSV" && $OVERWRITE -eq 0 ]]; then
        echo "[✓] RTT CSV already exists, skipping: $RTT_CSV"
    else
        echo "[+] Running http_rtt.py..."
        python3 http_rtt.py -i "$INPUT_PCAP" -o "$RTT_CSV"
        echo "[+] RTT CSV saved: $RTT_CSV"
    fi

    # ==================================================
    # STEP 2 - Generate RTT distribution + graphs
    # ==================================================
    MAX_RTT=10000
    echo "[+] Running rtt.py for graphs + distribution (MAX_RTT=${MAX_RTT} ms)..."

    python3 rtt.py -i "$RTT_CSV" --max_rtt "$MAX_RTT" -o "$OUT_DIR"

    echo "-------------------------------------------"

done

echo ""
echo "==========================================="
echo "[✓] ALL PCAPS PROCESSED SUCCESSFULLY"
echo "==========================================="
