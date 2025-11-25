#!/usr/bin/env python3
import argparse
import os
import json
import multiprocessing
from concurrent.futures import ProcessPoolExecutor
import re
from collections import defaultdict
import shutil

# -----------------------------------------------------------
# Protocol dictionary (YOUR LIST + common DC ports)
# -----------------------------------------------------------

PROTOCOL_MAP = {
    20: "ftp-data",
    21: "ftp",
    22: "ssh",
    23: "telnet",
    25: "smtp",
    53: "dns",
    67: "dhcp",
    68: "dhcp",
    80: "http",
    110: "pop3",
    111: "rpcbind",
    123: "ntp",
    143: "imap",
    161: "snmp",
    162: "snmptrap",
    389: "ldap",
    443: "https",
    445: "smb",
    514: "syslog",
    554: "rtsp",
    587: "smtp-submission",
    631: "ipp",
    636: "ldaps",
    873: "rsync",
    3306: "mysql",
    5432: "pgsql",
    11211: "memcache",
    1883: "mqtt",
    500: "isakmp",

    # DC ports
    8080: "http-alt",
    8443: "https-alt",
    9200: "elasticsearch",
    6379: "redis",
    9092: "kafka",
    27017: "mongodb",
    27018: "mongodb",
    27019: "mongodb",
}

# -----------------------------------------------------------
# Helpers
# -----------------------------------------------------------

IP_PORT_REGEX = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3}):(\d+)")

def extract_ip_port(line):
    m = IP_PORT_REGEX.search(line)
    if m:
        return m.group(1), int(m.group(2))
    return None, None

def clean_folder(folder):
    if os.path.isdir(folder) and not os.listdir(folder):
        shutil.rmtree(folder)


# -----------------------------------------------------------
# Worker function (must be TOP LEVEL for multiprocessing)
# -----------------------------------------------------------

def process_file(args):
    input_file, output_dir = args

    basename = os.path.splitext(os.path.basename(input_file))[0]
    file_output_dir = os.path.join(output_dir, basename)
    os.makedirs(file_output_dir, exist_ok=True)

    unique_ports = set()
    protocol_files = defaultdict(lambda: {"ips": set(), "sockets": set()})
    master_entries = []  # master file entries (IP, port, protocol)

    total_lines = 0
    ip_count = 0
    socket_count = 0

    with open(input_file, "r") as f:
        for line in f:
            total_lines += 1
            ip, port = extract_ip_port(line)
            if not ip or not port:
                continue

            socket = f"{ip}:{port}"
            unique_ports.add(port)

            # Determine protocol, default to "unknown"
            proto_name = PROTOCOL_MAP.get(port, "unknown")

            # If known, store in protocol_files
            if proto_name != "unknown":
                protocol_files[proto_name]["ips"].add(ip)
                protocol_files[proto_name]["sockets"].add(socket)
                ip_count += 1
                socket_count += 1

            # Add to master file (all entries)
            master_entries.append(f"{ip}\t{port}\t{proto_name}\n")

    # -----------------------------------------------------------
    # Write <basename>_port.txt
    # -----------------------------------------------------------

    port_file = os.path.join(file_output_dir, f"{basename}_port.txt")
    with open(port_file, "w") as pf:
        for p in sorted(unique_ports):
            pf.write(str(p) + "\n")

    # -----------------------------------------------------------
    # Write protocol folders (only known protocols)
    # -----------------------------------------------------------

    for proto, data in protocol_files.items():
        proto_dir = os.path.join(file_output_dir, proto)
        os.makedirs(proto_dir, exist_ok=True)

        ip_file = os.path.join(proto_dir, f"{basename}_ip.txt")
        socket_file = os.path.join(proto_dir, f"{basename}_socket.txt")

        with open(ip_file, "w") as f:
            for ip in sorted(data["ips"]):
                f.write(ip + "\n")

        with open(socket_file, "w") as f:
            for s in sorted(data["sockets"]):
                f.write(s + "\n")

        clean_folder(proto_dir)

    # -----------------------------------------------------------
    # Write master file
    # -----------------------------------------------------------
    master_file = os.path.join(file_output_dir, f"{basename}_master.txt")
    with open(master_file, "w") as mf:
        mf.write("IP\tPort\tProtocol\n")
        for entry in master_entries:
            mf.write(entry)

    # -----------------------------------------------------------
    # Write stats.json
    # -----------------------------------------------------------

    stats = {
        "file": input_file,
        "total_lines": total_lines,
        "unique_ports": len(unique_ports),
        "matched_protocols": list(protocol_files.keys()),
        "ip_entries": ip_count,
        "socket_entries": socket_count,
    }

    with open(os.path.join(file_output_dir, "stats.json"), "w") as jf:
        json.dump(stats, jf, indent=4)

    return input_file




# -----------------------------------------------------------
# Main
# -----------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Classify ports and create protocol folders.")
    parser.add_argument("-i", "--input", required=True, help="Input file OR folder")
    parser.add_argument("-o", "--output", required=True, help="Output folder")
    args = parser.parse_args()

    input_path = args.input
    output_dir = args.output
    os.makedirs(output_dir, exist_ok=True)

    # auto worker count
    workers = max(1, multiprocessing.cpu_count() - 1)

    # build file list
    files = []
    if os.path.isdir(input_path):
        for f in os.listdir(input_path):
            if f.lower().endswith(".txt"):
                files.append(os.path.join(input_path, f))
    else:
        files = [input_path]

    # prepare argument list for multiprocessing
    arg_list = [(f, output_dir) for f in files]

    # run workers
    with ProcessPoolExecutor(max_workers=workers) as exe:
        list(exe.map(process_file, arg_list))

    print(f"[+] Completed processing {len(files)} files.")


if __name__ == "__main__":
    main()
