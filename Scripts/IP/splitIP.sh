#!/bin/bash
# ===============================================================
#  Script Name : splitIPs.sh
#  Description : 
#      This script processes text files containing IP addresses and
#      ensures that each line has exactly one valid IPv4 address.
#      It removes duplicates, invalid entries, and can process a
#      single file or an entire directory of .txt files.
#
#  Features:
#      • Handles mixed separators (space, comma, tab, or pipe).
#      • Removes duplicate and empty lines.
#      • Validates only proper IPv4 addresses.
#      • Can overwrite original files or create cleaned versions.
#
#  ---------------------------------------------------------------
#  Usage:
#      ./splitIPs.sh [OPTIONS]
#
#  Options:
#      -f <file>        Process a single input file.
#      -d <directory>   Process all .txt files in the directory.
#      -o <file>        Specify output filename (only for -f mode).
#      -w               Overwrite original file(s) after cleaning.
#      -h               Show help message.
#
#  ---------------------------------------------------------------
#  Examples:
#      # 1. Clean a single file and save as <input>_cleaned.txt
#      ./splitIPs.sh -f all_ips.txt
#
#      # 2. Clean a single file and overwrite original
#      ./splitIPs.sh -f all_ips.txt -w
#
#      # 3. Clean all .txt files in a folder
#      ./splitIPs.sh -d /path/to/folder
#
#      # 4. Clean all .txt files in a folder and overwrite originals
#      ./splitIPs.sh -d /path/to/folder -w
#
#  ---------------------------------------------------------------
#  Output:
#      • Creates a new file named "<original>_cleaned.txt" (default)
#      • or overwrites the original file if -w is used
#
#  Author  : Mayank Singh
#  Version : 1.0
#  Date    : 2025-11-13
# ===============================================================


INPUT_FILE=""
INPUT_DIR=""
OUTPUT_FILE=""
OVERWRITE=false

usage() {
    echo "Usage: $0 [-f <input_file> | -d <input_directory>] [-o <output_file>] [-w]"
    echo ""
    echo "Options:"
    echo "  -f <file>       Specify a single input file to process."
    echo "  -d <directory>  Specify a directory containing .txt files to process."
    echo "  -o <file>       Specify output file name (only for -f mode)."
    echo "  -w              Overwrite the original file(s) with cleaned content."
    echo "  -h              Show this help message."
    echo ""
    echo "Examples:"
    echo "  $0 -f all_ips.txt -o cleaned.txt"
    echo "  $0 -d /path/to/folder"
    echo "  $0 -d /path/to/folder -w"
    exit 1
}

# --- Parse arguments ---
while getopts ":f:d:o:wh" opt; do
    case ${opt} in
        f)
            INPUT_FILE="$OPTARG"
            ;;
        d)
            INPUT_DIR="$OPTARG"
            ;;
        o)
            OUTPUT_FILE="$OPTARG"
            ;;
        w)
            OVERWRITE=true
            ;;
        h)
            usage
            ;;
        \?)
            echo "Invalid option: -$OPTARG" >&2
            usage
            ;;
        :)
            echo "Option -$OPTARG requires an argument." >&2
            usage
            ;;
    esac
done

# --- Validate input ---
if [ -z "$INPUT_FILE" ] && [ -z "$INPUT_DIR" ]; then
    echo "Error: You must specify either -f (file) or -d (directory)."
    usage
fi

# --- Function: check valid IPv4 ---
is_valid_ipv4() {
    local ip=$1
    # Must match format n.n.n.n where each n is 0–255
    if [[ $ip =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
        for octet in ${ip//./ }; do
            if ((octet < 0 || octet > 255)); then
                return 1
            fi
        done
        return 0
    fi
    return 1
}

# --- Function to clean IP file ---
clean_ips() {
    local infile="$1"
    local outfile="$2"

    echo "Processing: $infile"

    # Replace commas, pipes, tabs, or spaces with newlines, then keep only valid IPv4s
    cat "$infile" \
        | tr ',| \t' '\n' \
        | awk NF \
        | sort -u \
        | while read -r ip; do
            if is_valid_ipv4 "$ip"; then
                echo "$ip"
            fi
        done > "$outfile"

    echo "✅ Cleaned valid IPv4s saved to: $outfile"
}

# --- File mode ---
if [ -n "$INPUT_FILE" ]; then
    if [ ! -f "$INPUT_FILE" ]; then
        echo "Error: File '$INPUT_FILE' not found!"
        exit 1
    fi

    if [ "$OVERWRITE" = true ]; then
        TMP_FILE=$(mktemp)
        clean_ips "$INPUT_FILE" "$TMP_FILE"
        mv "$TMP_FILE" "$INPUT_FILE"
        echo "✅ Overwritten original file: $INPUT_FILE"
    else
        OUTPUT_FILE=${OUTPUT_FILE:-"$(basename "$INPUT_FILE" .txt)_cleaned.txt"}
        clean_ips "$INPUT_FILE" "$OUTPUT_FILE"
    fi
fi

# --- Directory mode ---
if [ -n "$INPUT_DIR" ]; then
    if [ ! -d "$INPUT_DIR" ]; then
        echo "Error: Directory '$INPUT_DIR' not found!"
        exit 1
    fi

    for file in "$INPUT_DIR"/*.txt; do
        [ -f "$file" ] || continue
        BASENAME=$(basename "$file")
        if [ "$OVERWRITE" = true ]; then
            TMP_FILE=$(mktemp)
            clean_ips "$file" "$TMP_FILE"
            mv "$TMP_FILE" "$file"
            echo "✅ Overwritten: $file"
        else
            OUTPUT_PATH="$INPUT_DIR/${BASENAME%.txt}_cleaned.txt"
            clean_ips "$file" "$OUTPUT_PATH"
        fi
    done
fi

echo "--------------------------------------------------"
echo "🎯 All tasks completed successfully."
