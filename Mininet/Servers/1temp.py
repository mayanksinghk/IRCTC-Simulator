#!/usr/bin/env python3
import socket
import ssl
import threading
import queue
import argparse

# ================= Configuration ==================
HOST = "10.0.3.1"       # TLS server listens on all interfaces
PORT = 5000            # TLS server port

WAF_IP = "10.0.3.2"   # WAF IP
WAF_PORT = 8080        # WAF port

DEFAULT_WAF_CONNECTIONS = 10  # Number of persistent TCP connections to WAF
TLS_VERSION = "TLSv1.3"       # Default TLS version
# ==================================================

# TLS version mapping
TLS_VERSIONS = {
    "TLSv1": ssl.PROTOCOL_TLSv1,
    "TLSv1.1": ssl.PROTOCOL_TLSv1_1,
    "TLSv1.2": ssl.PROTOCOL_TLSv1_2,
    "TLSv1.3": ssl.PROTOCOL_TLS_SERVER,
}

# Global queue to forward messages to WAF
waf_queue = queue.Queue()


# ================= WAF Connection Pool ==================
class WAFConnectionPool:
    def __init__(self, ip, port, pool_size=10):
        self.ip = ip
        self.port = port
        self.pool_size = pool_size
        self.connections = []
        self.lock = threading.Lock()
        self.next_conn = 0
        self._init_pool()

    def _init_pool(self):
        for _ in range(self.pool_size):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((self.ip, self.port))
            self.connections.append(s)
        print(f"[+] Initialized WAF connection pool with {self.pool_size} connections")

    def send(self, msg: bytes):
        """Send message to WAF using round-robin"""
        with self.lock:
            conn = self.connections[self.next_conn]
            self.next_conn = (self.next_conn + 1) % self.pool_size
        # Simple length-prefixed framing
        length_prefix = len(msg).to_bytes(4, byteorder='big')
        conn.sendall(length_prefix + msg)


def waf_worker():
    """Optional: separate thread to process messages from queue"""
    while True:
        msg = waf_queue.get()
        if msg is None:
            break
        waf_pool.send(msg)


# ================= TLS Client Handler ==================
def handle_client(conn, addr, context):
    """Handle a TLS client connection"""
    with context.wrap_socket(conn, server_side=True) as tls_conn:
        print(f"[+] TLS handshake completed with {addr}")
        while True:
            try:
                data = tls_conn.recv(4096)
                if not data:
                    print(f"[-] Client {addr} disconnected")
                    break
                print(f"[>] Received from {addr}: {data.decode(errors='ignore')}")
                tls_conn.sendall(b"ACK: " + data)  # Optional ACK to client

                # Forward to WAF (unsecured)
                waf_queue.put(data)

            except ssl.SSLError as e:
                print(f"[!] SSL error with {addr}: {e}")
                break
            except ConnectionResetError:
                print(f"[-] Client {addr} forcibly closed connection")
                break


# ================= Main Server ==================
def main(tls_version, waf_conn_count):
    # TLS context
    if tls_version == "TLSv1.3":
        context = ssl.SSLContext(TLS_VERSIONS[tls_version])
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.maximum_version = ssl.TLSVersion.TLSv1_3
    else:
        context = ssl.SSLContext(TLS_VERSIONS[tls_version])

    context.load_cert_chain(certfile="server.crt", keyfile="server.key")

    # Initialize WAF connection pool
    global waf_pool
    waf_pool = WAFConnectionPool(WAF_IP, WAF_PORT, pool_size=waf_conn_count)

    # Start WAF worker thread
    threading.Thread(target=waf_worker, daemon=True).start()

    # Start TLS server
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.bind((HOST, PORT))
        server_sock.listen()
        print(f"[+] TLS server listening on {HOST}:{PORT}, TLS version {tls_version}")

        while True:
            client_conn, client_addr = server_sock.accept()
            threading.Thread(target=handle_client, args=(client_conn, client_addr, context), daemon=True).start()


# ================= Command-line Interface ==================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tls", choices=["TLSv1", "TLSv1.1", "TLSv1.2", "TLSv1.3"], default=TLS_VERSION)
    parser.add_argument("--waf-conns", type=int, default=DEFAULT_WAF_CONNECTIONS,
                        help="Number of persistent TCP connections to WAF")
    args = parser.parse_args()
    main(args.tls, args.waf_conns)
