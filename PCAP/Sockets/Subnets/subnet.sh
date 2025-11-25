#!/bin/bash

# ---------------------------------------------------
# Parse flags
# ---------------------------------------------------
while [[ $# -gt 0 ]]; do
    case "$1" in
        -i|--input)
            INPUT="$2"
            shift 2
            ;;
        -s|--subnets)
            SUBNET_SRC="$2"
            shift 2
            ;;
        -o|--output)
            OUTPUT="$2"
            shift 2
            ;;
        -m|--mode)
            MODE="$2"
            shift 2
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
    esac
done

if [[ -z "$INPUT" || -z "$SUBNET_SRC" || -z "$OUTPUT" || -z "$MODE" ]]; then
    echo "Usage:"
    echo "  $0 -i <file|folder|pcap> -s <subnets or file> -o <output or folder> -m <text|pcap|folder>"
    exit 1
fi


# ---------------------------------------------------
# Load subnets
# ---------------------------------------------------
if [[ -f "$SUBNET_SRC" ]]; then
    SUBNETS=($(cat "$SUBNET_SRC"))
else
    SUBNETS=($SUBNET_SRC)
fi


# ---------------------------------------------------
# Function: Filter a single file and output ONLY IPs
# ---------------------------------------------------
filter_file() {
    local INPUT_FILE="$1"
    local OUTPUT_FILE="$2"
    local FILEMODE="$3"

    # Extract IPs if PCAP mode
    if [[ "$FILEMODE" == "pcap" ]]; then
        RAW_IP_FILE="${INPUT_FILE}_ips_raw.txt"

        tshark -r "$INPUT_FILE" -T fields -e ip.src -e ip.dst 2>/dev/null \
            | tr '\t' '\n' \
            | grep -Eo '([0-9]{1,3}\.){3}[0-9]{1,3}' \
            | sort -u > "$RAW_IP_FILE"

        INPUT_FILE="$RAW_IP_FILE"
    fi

    # Normalize → Extract only IPs
    NORMALIZED=$(mktemp)
    grep -Eo '([0-9]{1,3}\.){3}[0-9]{1,3}' "$INPUT_FILE" | sort -u > "$NORMALIZED"

    # If empty, skip
    if [[ ! -s "$NORMALIZED" ]]; then
        echo "[!] No valid IPs found in $INPUT_FILE (skipping)"
        return
    fi

    # Filter using AWK bitwise matching
    awk -v SUBNETS="${SUBNETS[*]}" '
        function ip2int(ip,   a) {
            split(ip, a, ".")
            return (a[1]*256^3) + (a[2]*256^2) + (a[3]*256) + a[4]
        }
        BEGIN {
            n = split(SUBNETS, s, " ")
            for (i=1; i<=n; i++) {
                split(s[i], part, "/")
                net[i] = ip2int(part[1])
                shift_bits = 32 - part[2]
                mask[i] = and(0xFFFFFFFF, compl(2^shift_bits - 1))
            }
        }
        {
            ip = $0
            ipval = ip2int(ip)
            for (i=1; i<=n; i++) {
                if ((and(ipval, mask[i])) == (and(net[i], mask[i]))) {
                    print ip
                    break
                }
            }
        }
    ' "$NORMALIZED" | sort -u > "$OUTPUT_FILE"

    echo "[+] Saved: $OUTPUT_FILE"
}



# ---------------------------------------------------
# Folder Mode
# ---------------------------------------------------
if [[ "$MODE" == "folder" ]]; then
    echo "[+] Folder mode activated."

    mkdir -p "$OUTPUT"

    for f in "$INPUT"/*; do
        [[ -f "$f" ]] || continue

        filename=$(basename -- "$f")
        extension="${filename##*.}"

        case "$extension" in
            txt)
                echo "[+] Processing TEXT: $f"
                filter_file "$f" "$OUTPUT/${filename%.txt}_filtered.txt" "text"
                ;;
            pcap|pcapng)
                echo "[+] Processing PCAP: $f"
                filter_file "$f" "$OUTPUT/${filename}_filtered.txt" "pcap"
                ;;
            *)
                echo "[!] Skipping unsupported file: $f"
                ;;
        esac
    done

    echo "[+] Folder processing complete."
    exit 0
fi




# ---------------------------------------------------
# Single file mode (text or pcap)
# ---------------------------------------------------
filter_file "$INPUT" "$OUTPUT" "$MODE"
