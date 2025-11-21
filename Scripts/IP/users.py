import ipaddress
import argparse
import os

# ---------------------------- CONFIG ----------------------------
# Reserved and registered ports (0-1023 reserved, 1024-49151 registered)
RESERVED_PORTS = set(range(0, 1024))
REGISTERED_PORTS = set(range(1024, 49152))

# Invalid IPs that cannot be clients
invalid_ips = {"0.0.0.0", "255.255.255.255"}
# ----------------------------------------------------------------

def filter_public_ips(ip_str):
    """
    Return True if the IP is a public IP (i.e., valid client IP)
    Removes private, loopback, link-local, multicast, reserved addresses
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False

    if ip_str in invalid_ips:
        return False
    return ip.is_global  # only public IPs

def is_port_valid(port_str):
    """Check if port is valid (not reserved or registered)"""
    try:
        port = int(port_str)
    except ValueError:
        return False
    if port in RESERVED_PORTS or port in REGISTERED_PORTS:
        return False
    return True

def process_file(input_file):
    valid_sockets = []
    valid_ips = set()

    with open(input_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue  # skip empty lines
            # split multiple sockets in one line by space or comma
            sockets = [s.strip() for s in line.replace(',', ' ').split()]
            for sock in sockets:
                if ':' not in sock:
                    continue
                ip, port = sock.split(':')
                ip, port = ip.strip(), port.strip()
                if filter_public_ips(ip) and is_port_valid(port):
                    valid_sockets.append(f"{ip}:{port}")
                    valid_ips.add(ip)

    return valid_sockets, valid_ips

def write_output(base_output_file, sockets, ips):
    # Generate separate file names
    socket_file = f"{os.path.splitext(base_output_file)[0]}_sockets.txt"
    ip_file = f"{os.path.splitext(base_output_file)[0]}_ips.txt"

    # Write sockets
    with open(socket_file, "w") as f:
        for s in sockets:
            f.write(s + "\n")

    # Write unique IPs
    with open(ip_file, "w") as f:
        for ip in ips:
            f.write(ip + "\n")

    return socket_file, ip_file

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Filter socket addresses from input file.")
    parser.add_argument("-f", "--input_file", required=True, help="Input text file with socket addresses")
    parser.add_argument("-o", "--output_file", required=True, help="Base name for output files")
    args = parser.parse_args()

    sockets, ips = process_file(args.input_file)
    socket_file, ip_file = write_output(args.output_file, sockets, ips)
    print(f"Filtering complete.\nSockets saved to '{socket_file}'\nUnique IPs saved to '{ip_file}'")
