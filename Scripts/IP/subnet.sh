#!/usr/bin/env bash
# ===============================================================
#  Script Name : filterSubnets.sh
#  Description :
#      Extracts IP addresses from one or more text files that belong
#      to one or more subnets (CIDR). Works for single file or folder.
# ===============================================================

usage() {
    grep '^#' "$0" | cut -c 3-
    exit 1
}

# --- Parse options ---
INPUT=""
SUBNETS=""
OUTPUT_FILE="combined_filtered_IPs.txt"

while getopts ":i:s:o:h" opt; do
    case $opt in
        i) INPUT="$OPTARG" ;;
        s) SUBNETS="$OPTARG" ;;
        o) OUTPUT_FILE="$OPTARG" ;;
        h) usage ;;
        \?) echo "Invalid option: -$OPTARG" >&2; usage ;;
        :) echo "Option -$OPTARG requires an argument." >&2; usage ;;
    esac
done

if [ -z "$INPUT" ] || [ -z "$SUBNETS" ]; then
    echo "Error: -i <input> and -s <subnets> are required." >&2
    usage
fi

# --- Ensure ipcalc exists ---
if ! command -v ipcalc >/dev/null 2>&1; then
    echo "ipcalc not found. Install it and re-run: sudo apt install ipcalc" >&2
    exit 1
fi

# --- Build subnet list ---
SUBNET_LIST=()
if [ -f "$SUBNETS" ]; then
    while IFS= read -r line; do
        # extract lines that look like CIDR
        if [[ $line =~ ([0-9]{1,3}\.){3}[0-9]{1,3}/[0-9]{1,2} ]]; then
            SUBNET_LIST+=("$line")
        fi
    done < "$SUBNETS"
else
    IFS=',' read -r -a SUBNET_LIST <<< "$SUBNETS"
fi

if [ ${#SUBNET_LIST[@]} -eq 0 ]; then
    echo "Error: No valid subnets found." >&2
    exit 1
fi

# --- Collect input files ---
FILES=()
if [ -d "$INPUT" ]; then
    while IFS= read -r -d '' f; do FILES+=("$f"); done < <(find "$INPUT" -type f -name '*.txt' -print0)
elif [ -f "$INPUT" ]; then
    FILES=("$INPUT")
else
    echo "Error: '$INPUT' is not a file or directory." >&2
    exit 1
fi

if [ ${#FILES[@]} -eq 0 ]; then
    echo "Error: No .txt input files found." >&2
    exit 1
fi

# --- helpers ---
ip_to_int() {
    local IFS=.
    read -r a b c d <<< "$1"
    printf '%u\n' $(( (a << 24) + (b << 16) + (c << 8) + d ))
}

is_valid_ipv4() {
    local ip=$1
    if [[ $ip =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
        local oct
        IFS=. read -r o1 o2 o3 o4 <<< "$ip"
        for oct in $o1 $o2 $o3 $o4; do
            if (( oct < 0 || oct > 255 )); then
                return 1
            fi
        done
        return 0
    fi
    return 1
}

# --- Build numeric ranges for each subnet ---
declare -A NET_INT BROAD_INT
for sn in "${SUBNET_LIST[@]}"; do
    info=$(ipcalc -n -b "$sn" 2>/dev/null)
    net=$(printf '%s\n' "$info" | awk -F: '/Network/ {print $2}' | tr -d ' ')
    broad=$(printf '%s\n' "$info" | awk -F: '/Broadcast/ {print $2}' | tr -d ' ')
    if [ -n "$net" ] && [ -n "$broad" ]; then
        NET_INT["$sn"]=$(ip_to_int "$net")
        BROAD_INT["$sn"]=$(ip_to_int "$broad")
    fi
done

# --- Process files and collect matches ---
: > "$OUTPUT_FILE"
for f in "${FILES[@]}"; do
    while IFS= read -r line || [ -n "$line" ]; do
        # split common separators into separate tokens
        for token in $(echo "$line" | tr ',|/:\t ' '\n' | awk NF | sort -u); do
            # token may have lost slash for CIDR if splitted; only test if IPv4
            if is_valid_ipv4 "$token"; then
                ipint=$(ip_to_int "$token")
                for sn in "${!NET_INT[@]}"; do
                    if (( ipint >= NET_INT["$sn"] && ipint <= BROAD_INT["$sn"] )); then
                        printf '%s\n' "$token" >> "$OUTPUT_FILE"
                        break
                    fi
                done
            fi
        done
    done < "$f"
done

# dedupe final output
if [ -s "$OUTPUT_FILE" ]; then
    sort -u -o "$OUTPUT_FILE" "$OUTPUT_FILE"
    echo "Done. Results in: $OUTPUT_FILE"
else
    echo "No matching IPs found. Output file is empty: $OUTPUT_FILE"
fi
