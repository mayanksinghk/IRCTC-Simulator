#!/usr/bin/env python3
import socket
import ssl
import argparse

PROXY_HOST = '127.0.0.1'
PROXY_PORT = 8000
CA_FILE = 'adc.crt'

def get_tls_version(version_str):
    version_map = {
        "1.0": ssl.TLSVersion.TLSv1,
        "1.1": ssl.TLSVersion.TLSv1_1,
        "1.2": ssl.TLSVersion.TLSv1_2,
        "1.3": ssl.TLSVersion.TLSv1_3
    }
    return version_map.get(version_str, ssl.TLSVersion.TLSv1_2)  # default TLS 1.2

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--host', default=PROXY_HOST)
    parser.add_argument('--port', type=int, default=PROXY_PORT)
    parser.add_argument('--cafile', default=CA_FILE)
    parser.add_argument('--tls-version', default='1.2', help='TLS version to use (1.0,1.1,1.2,1.3)')
    args = parser.parse_args()

    tls_version = get_tls_version(args.tls_version)

    raw = socket.create_connection((args.host, args.port))
    context = ssl.create_default_context(ssl.Purpose.SERVER_AUTH, cafile=args.cafile)
    context.minimum_version = tls_version
    context.maximum_version = tls_version

    tls_sock = context.wrap_socket(raw, server_hostname=args.host)
    print(f"[Client] Connected to TLS proxy using TLS {tls_sock.version()}")

    try:
        while True:
            msg = input("Enter message (quit to exit): ")
            if msg.lower() in ('quit', 'exit'):
                break
            tls_sock.sendall(msg.encode())
            data = tls_sock.recv(4096)
            if not data:
                print("[Client] Connection closed")
                break
            print("[Client] Received:", data.decode())
    finally:
        tls_sock.close()

if __name__ == "__main__":
    main()
