#!/usr/bin/env python3
import socket
import ssl
import argparse

SERVER_IP = "10.0.3.1"
SERVER_PORT = 443

TLS_VERSIONS = {
    "TLSv1": ssl.PROTOCOL_TLSv1,
    "TLSv1.1": ssl.PROTOCOL_TLSv1_1,
    "TLSv1.2": ssl.PROTOCOL_TLSv1_2,
    "TLSv1.3": ssl.PROTOCOL_TLS_CLIENT,  # we restrict below
}


def main(tls_version):
    if tls_version not in TLS_VERSIONS:
        raise ValueError(f"Unsupported TLS version: {tls_version}")

    if tls_version == "TLSv1.3":
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.maximum_version = ssl.TLSVersion.TLSv1_3
    else:
        context = ssl.SSLContext(TLS_VERSIONS[tls_version])

    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # skip verification for self-signed cert

    with socket.create_connection((SERVER_IP, SERVER_PORT)) as sock:
        with context.wrap_socket(sock, server_hostname=SERVER_IP) as tls_conn:
            print(f"[+] Connected with TLS version: {tls_conn.version()}")
            while True:
                msg = input("Enter message (or 'quit'): ")
                if msg.lower() == "quit":
                    break
                tls_conn.sendall(msg.encode())
                data = tls_conn.recv(1024)
                print(f"[<] ACK from server: {data.decode(errors='ignore')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tls", choices=["TLSv1", "TLSv1.1", "TLSv1.2", "TLSv1.3"], default="TLSv1.3")
    args = parser.parse_args()
    main(args.tls)
