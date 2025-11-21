#!/usr/bin/env python3

import argparse

def main():
    parser = argparse.ArgumentParser(description="Generate tshark command to filter pcap by IP list")
    parser.add_argument("-i", "--ip-file", required=True, help="File containing IPs (one per line)")
    parser.add_argument("-r", "--input-pcap", required=True, help="Input pcap file")
    parser.add_argument("-w", "--output-pcap", required=True, help="Output filtered pcap file")
    args = parser.parse_args()

    # Read IPs
    with open(args.ip_file) as f:
        ips = [line.strip() for line in f if line.strip()]

    if not ips:
        print("[!] No IPs found in the file")
        return

    # Create filter string
    filter_str = " || ".join(f"ip.addr == {ip}" for ip in ips)

    # Construct tshark command
    tshark_cmd = f'tshark -r "{args.input_pcap}" -Y "{filter_str}" -w "{args.output_pcap}"'

    print("\n[+] Generated tshark command:")
    print(tshark_cmd)
    print("\n[!] You can copy & run this command in your terminal")

if __name__ == "__main__":
    main()
