#!/usr/bin/env python3
from collections import defaultdict
from typing import List

INPUT_FILE = "12_get_http.txt"
FILTER_FILE = "10-filter.txt"


def load_filters(filter_file: str) -> List[List[str]]:
    """
    Load filters from file.
    Each line becomes a list of tokens (AND condition).
    """
    filters = []
    with open(filter_file, "r") as f:
        for line in f:
            line = line.strip()
            if line:
                filters.append(line.split())
    return filters


def match_filter(line: str, filter_tokens: List[str]) -> bool:
    """
    Returns True if ALL tokens in filter_tokens exist in line.
    """
    return all(token in line for token in filter_tokens)


def process_file(input_file: str, filters: List[List[str]]):
    """
    Stream input file line by line and count matches.
    """
    filter_count = defaultdict(int)
    total_lines = 0
    matched_lines = 0
    unmatched_lines = 0

    with open(input_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            total_lines += 1
            matched = False

            for flt in filters:
                if match_filter(line, flt):
                    key = " ".join(flt)
                    filter_count[key] += 1
                    matched = True

            if matched:
                matched_lines += 1
            else:
                unmatched_lines += 1

    return total_lines, matched_lines, unmatched_lines, filter_count


def print_summary(total, matched, unmatched, filter_count):
    print("\n========== FILTER SUMMARY ==========\n")

    print(f"Total lines processed       : {total}")
    print(f"Lines matched at least once : {matched}")
    print(f"Lines not matched           : {unmatched}")

    print("\n----- Per-filter counters -----")
    for flt, cnt in sorted(filter_count.items(), key=lambda x: x[1], reverse=True):
        print(f"{flt:40} : {cnt}")

    print("\n====================================\n")


def main():
    filters = load_filters(FILTER_FILE)
    total, matched, unmatched, filter_count = process_file(INPUT_FILE, filters)
    print_summary(total, matched, unmatched, filter_count)


if __name__ == "__main__":
    main()
