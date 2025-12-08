#!/usr/bin/env python3
'''
This script processes HTTP GET request URIs from a text file containing capture at 8-9, groups them in a logical grouping and cout their number. The results are saved to a txt file. It also generates a filter that can be used in tshark or wireshark to filter out packets related to these URIs which can be used for calculating round trip time and other analysis.
'''
import argparse
from urllib.parse import urlparse



#--------------- Helper Functions ---------------#

# ============================================================
# LOAD HOSTS FROM FILE
# ============================================================
def load_file(hosts_file: str) -> set:
    """Load hosts from a file into a set."""
    with open(hosts_file, 'r') as f:
        return set(line.strip() for line in f if line.strip())

def group_uri(uri: str) -> str:
    """Group URI into a logical grouping."""
    parsed_uri = urlparse(uri)
    list_uri_group = {
        
    }

# ============================================================
# PROCESS HTTP INPUT TXT FILES
# ============================================================
def process_http_file(input_file: str, verbose: bool) -> dict:
    """Process the HTTP input file and count URIs."""
    uri_counts = {}
    table = str.maketrans({' ': ' '})
    count = 0

    with open(input_file, 'r') as f:
        for line in f:
            parts = line.strip().translate(table).split()
            if len(parts) != 1:
                print(f"[!] Malformed line skipped: {line.strip()}")
                continue  # Skip malformed lines

            
            uri = parts[0]

    if verbose:
        print(f"[+] Processed {count} lines from {input_file}")
    return uri_counts

# ============================================================
# MAIN FUNCTION
# ============================================================
def main():
    argparser = argparse.ArgumentParser(description="Count unique HTTP GET request URIs in a PCAP file.")
    argparser.add_argument("-i", "--input", required=True, help="Input PCAP file")
    argparser.add_argument("-o", "--output", default="output.csv", help="Output CSV file")
    argparser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    args = argparser.parse_args()


    # Load input file 
    input = load_file(args.input)
    uri_counts = process_http_file(args.input, args.verbose)
    if args.verbose:
        print(f"[+] Loaded {len(input)} GET request from {args.input}")
        print(f"[+] Processed {len(uri_counts)} unique grouping of URIs.")
        for host, count in uri_counts.items():
            print(f"    Host: {host}, Count: {count}")
    
    # Write output to CSV
    with open(args.output, 'w') as out_file:
        out_file.write("Host,Count\n")
        for host, count in uri_counts.items():
            out_file.write(f"{host},{count}\n")
    if args.verbose:
        print(f"[+] Output written to {args.output}")




if __name__ == "__main__":
    main()


# Run the script with appropriate arguments to process HTTP URIs from a PCAP file.
# ./http_detail.py -i input.txt -o output.csv -f hosts.txt -v