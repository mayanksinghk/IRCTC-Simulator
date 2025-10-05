#!/usr/bin/env python3
import socket
import ssl
import threading
import argparse

LISTEN_HOST = '127.0.0.1'
LISTEN_PORT = 8000

BACKEND_HOST = '127.0.0.1'
BACKEND_PORT = 9000

CERT_FILE = 'adc.crt'
KEY_FILE = 'adc.key'

def log(direction, data):
    print(f"[{direction}] {len(data)} bytes: {data!r}")

def forward(src, dst, direction):
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            log(direction, data)
            dst.sendall(data)
    except Exception:
        pass
    finally:
        try:
            dst.shutdown(socket.SHUT_WR)
        except Exception:
            pass

def handle_connection(client_sock, addr):
    print(f"[Proxy] Accepted TLS client {addr}")

    # Connect to backend server (plain TCP)
    backend_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    backend_sock.connect((BACKEND_HOST, BACKEND_PORT))
    print(f"[Proxy] Connected to backend {BACKEND_HOST}:{BACKEND_PORT}")

    # Forward traffic bidirectionally
    t1 = threading.Thread(target=forward, args=(client_sock, backend_sock, "Client->Backend"), daemon=True)
    t2 = threading.Thread(target=forward, args=(backend_sock, client_sock, "Backend->Client"), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    client_sock.close()
    backend_sock.close()
    print(f"[Proxy] Closed connection for {addr}")

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
    parser.add_argument('--listen-host', default=LISTEN_HOST)
    parser.add_argument('--listen-port', type=int, default=LISTEN_PORT)
    parser.add_argument('--backend-host', default=BACKEND_HOST)
    parser.add_argument('--backend-port', type=int, default=BACKEND_PORT)
    parser.add_argument('--cert', default=CERT_FILE)
    parser.add_argument('--key', default=KEY_FILE)
    parser.add_argument('--tls-version', default='1.2', help='TLS version for client connections (1.0,1.1,1.2,1.3)')
    args = parser.parse_args()

    tls_version = get_tls_version(args.tls_version)

    # TLS context for server-side (accept TLS from client)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=args.cert, keyfile=args.key)
    context.minimum_version = tls_version
    context.maximum_version = tls_version

    # Listen
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((args.listen_host, args.listen_port))
    sock.listen(5)
    print(f"[Proxy] Listening on {args.listen_host}:{args.listen_port} (TLS {args.tls_version})")

    while True:
        client, addr = sock.accept()
        try:
            tls_client = context.wrap_socket(client, server_side=True)
        except ssl.SSLError as e:
            print(f"[Proxy] TLS handshake failed for {addr}: {e}")
            client.close()
            continue
        threading.Thread(target=handle_connection, args=(tls_client, addr), daemon=True).start()

if __name__ == "__main__":
    main()
