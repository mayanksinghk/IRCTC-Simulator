#!/bin/bash

API_LOOKUP=1
API_URL="https://api.maclookup.app/v2/macs/"
CACHE_FILE="mac_vendor_cache.txt"

echo "[INFO] Starting MAC Statistics Processor"

# Ensure cache exists
touch "$CACHE_FILE"

lookup_vendor() {
    mac=$1
    mac_upper=$(echo "$mac" | tr '[:lower:]' '[:upper:]')

    # Check cache first
    if grep -q "^$mac_upper," "$CACHE_FILE"; then
        grep "^$mac_upper," "$CACHE_FILE" | cut -d',' -f2-
        return
    fi

    # Log to STDERR so CSV is not polluted
    echo "[LOOKUP] Fetching vendor for $mac_upper ..." >&2

    # API lookup
    json=$(curl -s "${API_URL}${mac_upper}")

    vendor=$(echo "$json" | sed -n 's/.*"company":"\([^"]*\)".*/\1/p')

    [ -z "$vendor" ] && vendor="Unknown"

    # Cache result
    echo "$mac_upper,$vendor" >> "$CACHE_FILE"

    echo "$vendor"
}


export -f lookup_vendor
export API_LOOKUP
export API_URL
export CACHE_FILE

process_pcap() {
    PCAP="$1"
    BASENAME=$(basename "$PCAP" .pcap)
    OUT="${BASENAME}_mac.csv"
    TMP="${BASENAME}.tmp"
    UNSORTED="${BASENAME}_unsorted.csv"

    echo "[INFO][$PCAP] Extracting frames..."

    tshark -r "$PCAP" -Y "not (eth.dst[0] & 1)" \
        -T fields -e eth.src -e eth.dst -e frame.len \
        2>/dev/null > "$TMP"

    echo "[INFO][$PCAP] Processing extracted data..."

    # AWK for speed
    awk '
        BEGIN { FS="\t" }
        {
            src=tolower($1)
            dst=tolower($2)
            bytes=$3+0

            src_pkts[src]++
            src_bytes[src]+=bytes

            dst_pkts[dst]++
            dst_bytes[dst]+=bytes

            total_pkts[src]++
            total_bytes[src]+=bytes

            total_pkts[dst]++
            total_bytes[dst]+=bytes
        }
        END {
            for (mac in total_pkts) {
                print mac"," \
                      (src_pkts[mac]+0)","(src_bytes[mac]+0)"," \
                      (dst_pkts[mac]+0)","(dst_bytes[mac]+0)"," \
                      (total_pkts[mac]+0)","(total_bytes[mac]+0)
            }
        }
    ' "$TMP" > "$UNSORTED"

    echo "[INFO][$PCAP] Adding vendor names..."

    echo "MAC,Vendor,Src_Pkts,Src_Bytes,Dst_Pkts,Dst_Bytes,Total_Pkts,Total_Bytes" > "$OUT"

    while IFS=',' read -r mac sp sb dp db tp tb; do
        vendor="Unknown"
        if [ "$API_LOOKUP" -eq 1 ]; then
            vendor=$(lookup_vendor "$mac")
        fi
        echo "$mac,$vendor,$sp,$sb,$dp,$db,$tp,$tb" >> "$OUT"
    done < "$UNSORTED"

    echo "[INFO][$PCAP] Sorting by total bytes..."

    { head -n 1 "$OUT"; tail -n +2 "$OUT" | sort -t, -k8,8nr; } > "${OUT}.sorted"
    mv "${OUT}.sorted" "$OUT"

    rm -f "$TMP" "$UNSORTED"

    echo "[INFO][$PCAP] CSV ready → $OUT"
}

export -f process_pcap

# MAIN
if [ $# -lt 1 ]; then
    echo "Usage: $0 file.pcap"
    echo "       $0 directory/"
    exit 1
fi

INPUT="$1"

if [ -d "$INPUT" ]; then
    echo "[INFO] Directory mode → parallel enabled"
    find "$INPUT" -type f -name "*.pcap" | parallel process_pcap
else
    echo "[INFO] Single file mode"
    process_pcap "$INPUT"
fi

echo "[INFO] All processing complete!"
