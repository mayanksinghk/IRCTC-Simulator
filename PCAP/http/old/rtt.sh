#!/bin/bash

# ============================================================
#  run_rtt.sh
#  Wrapper to optimize and run rtt.py by pre-counting packets
#  using tshark, then invoking Python with --total argument
#
#  Usage:
#      ./run_rtt.sh input.pcap output.csv
# ============================================================

set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 <input.pcap> <output.csv>"
    exit 1
fi

INPUT_PCAP="$1"
OUTPUT_CSV="$2"

if [ ! -f "$INPUT_PCAP" ]; then
    echo "[ERROR] Input pcap not found: $INPUT_PCAP"
    exit 1
fi

echo "============================================"
echo "[INFO] Starting RTT processing"
echo "[INFO] PCAP: $INPUT_PCAP"
echo "[INFO] Output: $OUTPUT_CSV"
echo "============================================"

# ------------------------------------------------------------
# STEP 1: Pre-count packets using tshark (fast & efficient)
# ------------------------------------------------------------

echo "[INFO] Counting packets using tshark..."
START_COUNT=$(date +%s)

PACKET_COUNT=$(tshark -r "$INPUT_PCAP"  | wc -l )

END_COUNT=$(date +%s)
COUNT_TIME=$((END_COUNT - START_COUNT))

echo "[INFO] Packet count completed in $COUNT_TIME sec"
echo "[INFO] Total packets detected: $PACKET_COUNT"


# ------------------------------------------------------------
# STEP 2: Run Python script with --total argument
# ------------------------------------------------------------

echo "--------------------------------------------"
echo "[INFO] Launching Python script..."
echo "[INFO] Passing total packets for ETA: $PACKET_COUNT"
echo "--------------------------------------------"

START_TIME=$(date +%s)

python3 rtt.py \
    -f "$INPUT_PCAP" \
    -o "$OUTPUT_CSV" \
    --total "$PACKET_COUNT"

END_TIME=$(date +%s)
TOTAL_TIME=$((END_TIME - START_TIME))

# ------------------------------------------------------------
# STEP 3: Final summary
# ------------------------------------------------------------

echo "============================================"
echo "[DONE] RTT Analysis Completed"
echo "[INFO] Total processing time: $TOTAL_TIME sec"
echo "[INFO] Output saved to: $OUTPUT_CSV"
echo "============================================"
