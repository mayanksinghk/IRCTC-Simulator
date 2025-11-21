#!/bin/bash

# Select the name of program you want to run on all your data
LOG_DIR="/home/mayank/Desktop/IRCTC/IRCTC-Simulator/Data/Analysis/Zeek"

# Running the program on all available logs
for file in "$LOG_DIR"/**/*.log ; do
    echo "Working with $file"
    OUTPUT="${file::-4}.csv"
    cat "$file" | zeek-cut -F ',' -d > "$OUTPUT"
done

echo "Done"

