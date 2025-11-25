#!/usr/bin/env python3
import argparse
import ipaddress
import os
import re
import subprocess
import tempfile


# -------------------------------------
# Extract IP and IP:PORT from text file
# -------------------------------------
def normalize_file(input_file):
    pattern = re.compile(r"(\d{1,3}(?:\.\d{1,3}){3})(?::(\d+))?")
    temp = tempfile.NamedTemporaryFile(delete=False, mode='w')
    seen = set()

    with open(input_file, "r", errors="ignore") as f:
        for line in f:
            matches = pattern.findall(line)
            for ip, port in matches:
                if port:
                    entry = f"{ip}:{port}"
                else:
                    entry = ip

                if entry not in seen:
                    seen.add(entry)
                    temp.write(entry + "\n")

    temp.close()
    return temp.name


# -------------------------------------
# Extract sockets from PCAP
# -------------------------------------
def normalize_pcap(pcap_file):
    temp = tempfile.NamedTemporaryFile(delete=False, mode='w')
    seen = set()

    cmd = [
        "tshark", "-r", pcap_file,
        "-T", "fields",
        "-e", "ip.src", "-e", "tcp.srcport", "-e", "udp.srcport"
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

    for line in proc.stdout:
        parts = line.strip().split("\t")
        ip = parts[0] if parts[0] else ""

        if not ip:
            continue

        tcp_port = parts[1] if len(parts) > 1 else ""
        udp_port = parts[2] if len(parts) > 2 else ""

        if tcp_port:
            entry = f"{ip}:{tcp_port}"
        elif udp_port:
            entry = f"{ip}:{udp_port}"
        else:
            entry = ip

        if entry not in seen:
            seen.add(entry)
            temp.write(entry + "\n")

    temp.close()
    return temp.name


# -------------------------------------
# Load subnets (direct or from file)
# -------------------------------------
def load_subnets(subnet_args):
    subnets = []
    for s in subnet_args:
        if os.path.isfile(s):
            with open(s) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    subnets.append(ipaddress.ip_network(line, strict=False))
        else:
            subnets.append(ipaddress.ip_network(s, strict=False))
    return subnets


# -------------------------------------
# Check if IP matches allowed subnets
# -------------------------------------
def ip_in_subnets(ip, subnet_list):
    try:
        ip_obj = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(ip_obj in net for net in subnet_list)


# -------------------------------------
# Filter into BOTH outputs: IP and Sockets
# -------------------------------------
def filter_normalized(norm_file, out_ip_file, out_socket_file, subnets):
    ip_results = set()
    socket_results = set()

    with open(norm_file) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            if ":" in line:
                ip, port = line.split(":", 1)
                socket_line = line
            else:
                ip = line
                port = None
                socket_line = None

            if not ip_in_subnets(ip, subnets):
                continue

            ip_results.add(ip)
            if socket_line:
                socket_results.add(socket_line)

    if ip_results:
        with open(out_ip_file, "w") as f:
            for x in sorted(ip_results):
                f.write(x + "\n")
        print(f"[+] Saved: {out_ip_file}")

    if socket_results:
        with open(out_socket_file, "w") as f:
            for x in sorted(socket_results):
                f.write(x + "\n")
        print(f"[+] Saved: {out_socket_file}")


# -------------------------------------
# Main
# -------------------------------------
def main():
    parser = argparse.ArgumentParser(description="Filter IPs and sockets based on subnets.")
    parser.add_argument("-i", "--input", help="Input text file")
    parser.add_argument("-d", "--directory", help="Folder mode")
    parser.add_argument("-p", "--pcap", help="PCAP mode")
    parser.add_argument("-o", "--outdir", required=True, help="Output folder")
    parser.add_argument("-s", "--subnets", nargs="+", required=True, help="Subnets or subnet file")

    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)
    subnets = load_subnets(args.subnets)

    # ---------------- PCAP MODE ----------------
    if args.pcap:
        print("[+] PCAP mode")
        norm = normalize_pcap(args.pcap)
        base = os.path.splitext(os.path.basename(args.pcap))[0]

        out_ip = os.path.join(args.outdir, f"{base}_ip.txt")
        out_sock = os.path.join(args.outdir, f"{base}_sockets.txt")

        filter_normalized(norm, out_ip, out_sock, subnets)
        return

    # ---------------- FOLDER MODE --------------
    if args.directory:
        print("[+] Folder mode")
        for f in os.listdir(args.directory):
            full = os.path.join(args.directory, f)
            if not os.path.isfile(full):
                continue

            print(f"[+] Processing: {f}")
            norm = normalize_file(full)

            base = os.path.splitext(f)[0]
            out_ip = os.path.join(args.outdir, f"{base}_ip.txt")
            out_sock = os.path.join(args.outdir, f"{base}_sockets.txt")

            filter_normalized(norm, out_ip, out_sock, subnets)
        return

    # ---------------- FILE MODE ----------------
    if args.input:
        print("[+] File mode")
        norm = normalize_file(args.input)

        base = os.path.splitext(os.path.basename(args.input))[0]
        out_ip = os.path.join(args.outdir, f"{base}_ip.txt")
        out_sock = os.path.join(args.outdir, f"{base}_sockets.txt")

        filter_normalized(norm, out_ip, out_sock, subnets)
        return

    print("No input mode selected.")


if __name__ == "__main__":
    main()
