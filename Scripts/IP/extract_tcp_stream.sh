#!/bin/bash
# Usage: ./extract_tcp_streams.sh input.pcap output_folder

PCAP_FILE="$1"
OUTPUT_DIR="$2"

if [[ -z "$PCAP_FILE" || -z "$OUTPUT_DIR" ]]; then
    echo "Usage: $0 input.pcap output_folder"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# --- Step 1: List all TCP stream numbers ---
echo "Listing TCP streams from $PCAP_FILE..."
STREAMS=$(tshark -r "$PCAP_FILE" -T fields -e tcp.stream | sort -n | uniq)

# --- Step 2: Extract each stream in parallel ---
echo "Extracting streams to $OUTPUT_DIR in parallel..."
export PCAP_FILE OUTPUT_DIR

echo "$STREAMS" | parallel -j $(nproc) '
    STREAM_NUM={}
    FILE="$OUTPUT_DIR/stream_$STREAM_NUM.pcap"
    echo "Extracting stream $STREAM_NUM -> $FILE"
    tshark -r "$PCAP_FILE" -Y "tcp.stream==$STREAM_NUM" -w "$FILE"
'

echo "✅ All streams extracted!"
