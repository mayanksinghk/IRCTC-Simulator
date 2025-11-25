#!/usr/bin/env python3
import argparse
import os
import csv
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
import re
from collections import defaultdict

# -----------------------------------------------------------
# Protocol dictionary
# -----------------------------------------------------------

PROTOCOL_MAP = {
    20: "ftp-data", 21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp",
    53: "dns", 67: "dhcp", 68: "dhcp", 80: "http", 110: "pop3",
    111: "rpcbind", 123: "ntp", 143: "imap", 161: "snmp",
    162: "snmptrap", 389: "ldap", 443: "https", 445: "smb",
    514: "syslog", 554: "rtsp", 587: "smtp-submission",
    631: "ipp", 636: "ldaps", 873: "rsync", 3306: "mysql",
    5432: "pgsql", 11211: "memcache", 1883: "mqtt", 500: "isakmp",
    8080: "http-alt", 8443: "https-alt", 9200: "elasticsearch",
    6379: "redis", 9092: "kafka",
    27017: "mongodb", 27018: "mongodb", 27019: "mongodb"
}

# -----------------------------------------------------------
# Regex Helper
# -----------------------------------------------------------

IP_PORT_REGEX = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d+)")

def extract_ip_port(line):
    m = IP_PORT_REGEX.search(line)
    if m:
        return m.group(1), int(m.group(2))
    return None, None


# -----------------------------------------------------------
# Load ASN CSV Mapping
# -----------------------------------------------------------

def load_asn_csv(csv_file):
    mapping = {}
    with open(csv_file, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ip = row["IP"].strip()
            mapping[ip] = {
                "asn": row["ASN"].strip(),
                "name": row["ASN Name"].strip()
            }
    return mapping


# -----------------------------------------------------------
# Worker Function
# -----------------------------------------------------------

def process_file(args):
    input_file, output_dir, asn_map = args

    basename = os.path.splitext(os.path.basename(input_file))[0]
    md_path = os.path.join(output_dir, f"{basename}.md")

    protocol_ips = defaultdict(set)

    # Read input line-by-line (streaming)
    with open(input_file, "r") as f:
        for line in f:
            ip, port = extract_ip_port(line)
            if not ip or not port:
                continue

            proto = PROTOCOL_MAP.get(port, None)
            if proto:
                protocol_ips[proto].add(ip)

    # -----------------------------------------------------------
    # Write Markdown Output
    # -----------------------------------------------------------

    with open(md_path, "w") as md:

        md.write(f"# Summary for {basename}\n\n")

        for proto, ips in sorted(protocol_ips.items()):

            md.write(f"### Protocol: {proto}\n")

            for ip in sorted(ips):
                if ip in asn_map:
                    asn = asn_map[ip]["asn"]
                    name = asn_map[ip]["name"]
                    md.write(f"- {ip} → ASN {asn} ({name})\n")
                else:
                    md.write(f"- {ip} → ASN Unknown\n")

            md.write("\n")

    return md_path


# -----------------------------------------------------------
# Main
# -----------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate Markdown summary with ASN mapping.")
    parser.add_argument("-i", "--input", required=True, help="Input file OR folder containing TXT")
    parser.add_argument("-o", "--output", required=True, help="Output folder")
    parser.add_argument("-a", "--asn", required=True, help="ASN CSV mapping file")

    args = parser.parse_args()

    os.makedirs(args.output, exist_ok=True)

    # Load ASN mapping CSV
    asn_map = load_asn_csv(args.asn)

    # Build list of TXT files
    if os.path.isdir(args.input):
        files = [
            os.path.join(args.input, f)
            for f in os.listdir(args.input)
            if f.endswith(".txt")
        ]
    else:
        files = [args.input]

    workers = max(1, multiprocessing.cpu_count() - 1)

    task_args = [
        (f, args.output, asn_map)
        for f in files
    ]

    with ProcessPoolExecutor(max_workers=workers) as exe:
        results = list(exe.map(process_file, task_args))

    print("[+] Generated Markdown files:")
    for r in results:
        print("   →", r)


if __name__ == "__main__":
    main()
