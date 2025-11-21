#!/bin/bash

# Define variables with default names (can be overridden by options)
FILE_NAME=""
OUTPUT_NAME=""
MODE=3  # Default: both source and destination IPs

# Function to display help information and exit
usage() {
    echo "Usage: $0 [OPTIONS]" >&2
    echo "Extracts unique source and/or destination IPs from a given PCAP file." >&2
    echo "" >&2
    echo "Options:" >&2
    echo "  -f <FILE>   Specify the input PCAP file (required)." >&2
    echo "  -o <FILE>   Specify the output file name (optional; auto-generated if not given)." >&2
    echo "  -m <MODE>   Mode selection:" >&2
    echo "              1 - Extract only source IPs" >&2
    echo "              2 - Extract only destination IPs" >&2
    echo "              3 - Extract both source and destination IPs (default)" >&2
    echo "  -h          Display this help message and exit." >&2
    exit 1
}

# --- Argument Parsing using getopts ---
while getopts ":hf:o:m:" opt; do
    case $opt in
        h)
            usage
            ;;
        f)
            FILE_NAME=$OPTARG
            ;;
        o)
            OUTPUT_NAME=$OPTARG
            ;;
        m)
            MODE=$OPTARG
            ;;
        :)
            echo "Error: Option -$OPTARG requires an argument." >&2
            usage
            ;;
        \?)
            echo "Error: Invalid option -$OPTARG" >&2
            usage
            ;;
    esac
done

shift $((OPTIND - 1))

# --- Validation ---
if [ -z "$FILE_NAME" ]; then
    echo "❌ Error: Input file must be specified using the -f option." >&2
    usage
fi

if [ ! -f "$FILE_NAME" ]; then
    echo "❌ Error: File '$FILE_NAME' not found!" >&2
    exit 1
fi

if ! [[ "$MODE" =~ ^[1-3]$ ]]; then
    echo "❌ Error: Invalid mode '$MODE'. Must be 1, 2, or 3." >&2
    usage
fi

# --- Determine mode label ---
case $MODE in
    1) MODE_LABEL="src" ;;
    2) MODE_LABEL="dest" ;;
    3) MODE_LABEL="all" ;;
esac

# --- Auto-generate output name if not provided ---
if [ -z "$OUTPUT_NAME" ]; then
    base_name=$(basename "$FILE_NAME" .pcap)
    OUTPUT_NAME="${base_name}_${MODE_LABEL}.txt"
fi

# --- Main Script Logic ---
echo "📂 Processing PCAP file: $FILE_NAME"
echo "⚙️  Mode: $MODE ($MODE_LABEL)"
echo "💾 Output file: $OUTPUT_NAME"

# Extract unique IPs based on mode
case $MODE in
    1)
        echo "🔍 Extracting Source IPs..."
        tshark -r "$FILE_NAME" -T fields -e ip.src -e tcp.srcport -e udp.srcport -Y "ip && (tcp || udp)" | awk '{if ($1!="") {if ($2!="") print $1":"$2; else if ($3!="") print $1":"$3;}}' | sort -u > "$OUTPUT_NAME"
        ;;
    2)
        echo "🔍 Extracting Destination IPs..."
        tshark -r "$FILE_NAME" -T fields -e ip.dst -e tcp.dstport -e udp.dstport -Y "ip && (tcp || udp)" | awk '{if ($1!="") {if ($2!="") print $1":"$2; else if ($3!="") print $1":"$3;}}' | sort -u > "$OUTPUT_NAME"
        ;;
    3)
        echo "🔍 Extracting Both Source and Destination IPs..."
        tshark -r "$FILE_NAME" -T fields -e ip.src -e tcp.srcport -e udp.srcport -e ip.dst -e tcp.dstport -e udp.dstport -Y "ip && (tcp || udp)" | awk '{if ($1!="") {if ($2!="") print $1":"$2; else if ($3!="") print $1":"$3;} if ($4!="") {if ($5!="") print $4":"$5; else if ($6!="") print $4":"$6;}}' | sort -u > "$OUTPUT_NAME"
        ;;
esac

# --- Summary ---
if [ -s "$OUTPUT_NAME" ]; then
    count=$(wc -l < "$OUTPUT_NAME")
    echo "✅ Done. Extracted $count unique IPs."
else
    echo "⚠️  No IPs found in this file."
fi

echo "📄 Results saved in: $OUTPUT_NAME"
