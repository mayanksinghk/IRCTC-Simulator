#!/bin/bash

# === Configuration ===
PROGRAM="ack_rtt.sh"  # Your main script
PCAP_DIR="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/Data/PCAP"
NEW_DIR_NAME="NetworkTransimissionTiming"

# === Derived directories ===
RESULT_DIR="${PCAP_DIR%/*}/${NEW_DIR_NAME}_${MODE_LABEL}"
mkdir -p "$RESULT_DIR"

echo "--------------------------------------------------"
echo "Input PCAP directory: $PCAP_DIR"
echo "Output directory: $RESULT_DIR"
echo "Program: $PROGRAM"
echo "--------------------------------------------------"

# === Run program for each pcap file ===
for file in "$PCAP_DIR"/*.pcap; do
    if [ -f "$file" ]; then
        base_name=$(basename "$file" .pcap)
        output_file="$RESULT_DIR/${base_name}_${MODE_LABEL}.txt"
        echo "Processing: $file → $output_file"
        ./"$PROGRAM" -f "$file" -o "$output_file" -m "$MODE"
    fi
done

# === Combine all results ===
UNIQUE_IP="$RESULT_DIR/all_unique_ip_${MODE_LABEL}.txt"

echo "Generating a master file with all unique IPs..."
cat "$RESULT_DIR"/*.txt | grep -v '^$' | sort -u > "$UNIQUE_IP"

if [ -s "$UNIQUE_IP" ]; then
    count=$(wc -l < "$UNIQUE_IP")
    echo "Done. Found $count unique IPs."
else
    echo "No IPs extracted from any capture."
fi

echo "--------------------------------------------------"
echo "Master unique IP list saved to: $UNIQUE_IP"
