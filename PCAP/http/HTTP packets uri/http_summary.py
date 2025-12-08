#!/usr/bin/env python3

import argparse
from urllib.parse import urlparse



#--------------- Helper Functions ---------------#

# ============================================================
# LOAD HOSTS FROM FILE
# ============================================================
def load_hosts(hosts_file: str) -> set:
    """Load hosts from a file into a set."""
    with open(hosts_file, 'r') as f:
        return set(line.strip() for line in f if line.strip())
    
# ============================================================
# PROCESS HTTP INPUT TXT FILES
# ============================================================
def process_http_file(input_file: str, mode: int, hosts: set, verbose: bool) -> dict:
    """Process the HTTP input file and count URIs based on the selected mode."""
    uri_counts = {}
    table = str.maketrans({
    # ',': ' ',
    ' ': ' '
    })
    count = 0

    with open(input_file, 'r') as f:
        for line in f:
            parts = line.strip().translate(table).split()
            if len(parts) != 1:
                print(f"[!] Malformed line skipped: {line.strip()}")
                continue  # Skip malformed lines
            
            uri = parts[0]
            host = urlparse(uri).hostname or ""

            if mode == 1:
                # Mode 1: Count http packets per host
                if host in hosts:
                    if host not in uri_counts:
                        uri_counts[host] = 0
                    uri_counts[host] += 1
            elif mode == 2:
                # Mode 2: Detailed count of URIs
                if uri not in uri_counts:
                    uri_counts[uri] = 0
                uri_counts[uri] += 1
            count += 1

    if verbose:
        print(f"[+] Processed {count} lines from {input_file}")
        u_counts = 0
        for uri, cnt in uri_counts.items():
            u_counts += cnt
        print(f"[+] Total unique URIs counted: {len(uri_counts)} with total count: {u_counts}")
    return uri_counts

# ============================================================
# MAIN FUNCTION
# ============================================================
def main():
    argparser = argparse.ArgumentParser(description="Count unique HTTP GET request URIs in a PCAP file.")
    argparser.add_argument("-i", "--input", required=True, help="Input PCAP file")
    argparser.add_argument("-o", "--output", default="get_uri_counts.csv", help="Output CSV file")
    argparser.add_argument("-m", "--mode", default=1, type=int, help="Host mode: 1 for counting http packets per host, 2 for getting a detailed count of URIs")
    argparser.add_argument("-f", "--hosts", help="File containing list of hosts to filter")
    argparser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose output")

    args = argparser.parse_args()

    # Host file required when mode=1
    if args.mode == 1 and not args.hosts:
        argparser.error("--hosts is required when --mode 1 is selected")

    # Load hosts if mode 1 is selected
    if args.mode == 1:
        hosts = load_hosts(args.hosts)
        uri_counts = process_http_file(args.input, args.mode, hosts, args.verbose)
        if args.verbose:
            print(f"[+] Loaded {len(hosts)} hosts from {args.hosts}")
            print(f"[+] Processed {len(uri_counts)} unique URIs.")
            for host, count in uri_counts.items():
                print(f"    Host: {host}, Count: {count}")
        
        # Write output to CSV
        with open(args.output, 'w') as out_file:
            out_file.write("Host,Count\n")
            for host, count in uri_counts.items():
                out_file.write(f"{host},{count}\n")
        if args.verbose:
            print(f"[+] Output written to {args.output}")

    else:
        hosts = None
        # Mode 2 does not require host filtering



if __name__ == "__main__":
    main()


# Run the script with appropriate arguments to process HTTP URIs from a PCAP file.
# ./http_summary.py -i ./Get/8-9_get_http.txt -f ./Hosts/8-9_unique_hosts.txt -o ./Output/8-9_get_summary.csv -v
# ./http_summary.py -i ./Get/10_get_http.txt -f ./Hosts/10_unique_hosts.txt -o ./Output/10_get_summary.csv -v
# ./http_summary.py -i ./Get/11_get_http.txt -f ./Hosts/11_unique_hosts.txt -o ./Output/11_get_summary.csv -v
# ./http_summary.py -i ./Get/12_get_http.txt -f ./Hosts/12_unique_hosts.txt -o ./Output/12_get_summary.csv -v