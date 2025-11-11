#!/usr/bin/env python3
import socket
import ssl
import threading
import queue
import argparse
import uuid
import struct
import logging

# ================= Configuration ==================
HOST = "10.0.3.1"       # TLS server listens here
PORT = 443               # TLS server port

WAF_IP = "10.0.3.2"     # WAF IP
WAF_PORT = 8080          # WAF port

DEFAULT_WAF_CONNECTIONS = 1  # Number of persistent TCP connections to WAF
TLS_VERSION = "TLSv1.3"       # Default TLS version
# ==================================================

# Configure basic logging to console
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Get a logger instance
logger = logging.getLogger(__name__)

# TLS version mapping
TLS_VERSIONS = {
    "TLSv1": ssl.PROTOCOL_TLSv1,
    "TLSv1.1": ssl.PROTOCOL_TLSv1_1,
    "TLSv1.2": ssl.PROTOCOL_TLSv1_2,
    "TLSv1.3": ssl.PROTOCOL_TLS_SERVER,
}

# Global queues and maps
waf_queue = queue.Queue()         # Messages to WAF
response_queue = queue.Queue()    # Responses from WAF
client_map = {}                   # client_id -> TLS client socket

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
            s.setblocking(False)  # Non-blocking for reading responses
            self.connections.append(s)
        logger.info(f"[+] Initialized WAF pool with {self.pool_size} connections")

    def send(self, msg: bytes):
        """Send message to WAF using round-robin"""
        with self.lock:
            conn = self.connections[self.next_conn]
            self.next_conn = (self.next_conn + 1) % self.pool_size
        length_prefix = len(msg).to_bytes(4, byteorder='big')
        conn.sendall(length_prefix + msg)

# ================= WAF Worker ==================
def waf_worker():
    """Send messages from queue to WAF"""
    while True:
        msg = waf_queue.get()
        if msg is None:
            break
        waf_pool.send(msg)

# ================= Helper: Read line from WAF ==================
def recv_all(conn, n):
    """Receive exactly n bytes from a socket, or None if connection closed"""
    data = b""
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        if not chunk:
            return None  # connection closed
        data += chunk
    return data

# ================= WAF Response Worker ==================
def waf_response_worker():
    """Read responses from WAF pool and send to correct TLS client"""
    while True:
        for idx, conn in enumerate(waf_pool.connections):
            try:
                logger.debug(f"[xxx]")
                # ---- Step 1: read 4-byte length prefix ----
                length_bytes = conn.recv(4)
                if not length_bytes:
                    continue

                msg_length = struct.unpack("!I", length_bytes)[0]
                logger.debug(f"[<] WAF[{idx}] expecting {msg_length} bytes")

                # ---- Step 2: read full message ----
                data = b""
                while len(data) < msg_length:
                    chunk = conn.recv(msg_length - len(data))
                    if not chunk:
                        break
                    data += chunk
                if not data:
                    continue

                # ---- Step 3: decode + parse ----
                msg = data.decode(errors="ignore")
                logger.debug(f"[<] WAF[{idx}] response: {msg}")

                if ':' not in msg:
                    logger.debug(f"[!] Invalid WAF message format: {msg}")
                    continue

                client_id, response_msg = msg.split(":", 1)
                logger.debug(f"Routing WAF response to client_id={client_id}")

                # ---- Step 4: route response to correct TLS client ----
                if client_id in client_map:
                    tls_conn = client_map[client_id]
                    logger.debug(f"[>] Sending to TLS client {client_id}, conn={tls_conn}")
                    tls_conn.sendall(response_msg.encode())
                else:
                    logger.debug(f"[!] Unknown client_id {client_id}, dropping message")

            except BlockingIOError:
                continue
            except Exception as e:
                logger.info(f"[!] WAF response error (conn[{idx}]): {e}")


# ================= TLS Client Handler ==================
def handle_client(conn, addr, context):
    """Handle a TLS client connection with proper response forwarding"""
    client_id = str(uuid.uuid4())  # Unique client ID
    response_q = queue.Queue()     # Queue for backend/WAF responses
    client_map[client_id] = response_q

    with context.wrap_socket(conn, server_side=True) as tls_conn:
        logger.info(f"[+] TLS handshake completed with {addr}, client_id={client_id}")

        def send_responses():
            """Send WAF/backend responses to client"""
            while True:
                msg = response_q.get()
                if msg is None:  # Sentinel to close thread
                    break
                try:
                    tls_conn.sendall(msg.encode())
                except Exception as e:
                    logger.info(f"[!] Error sending to client {addr}: {e}")
                    break

        threading.Thread(target=send_responses, daemon=True).start()

        try:
            while True:
                data = tls_conn.recv(4096)
                if not data:
                    logger.info(f"[-] Client {addr} disconnected")
                    break

                logger.debug(f"[>] Received from {addr}: {data.decode(errors='ignore')}")

                # Forward to WAF with client_id
                msg_to_waf = f"{client_id}:{data.decode(errors='ignore')}".encode()
                waf_queue.put(msg_to_waf)

        except ssl.SSLError as e:
            logger.info(f"[!] SSL error with {addr}: {e}")
        except ConnectionResetError:
            logger.info(f"[-] Client {addr} forcibly closed connection")
        finally:
            response_q.put(None)  # Stop send_responses thread
            del client_map[client_id]


# ================= Main Server ==================
def main(tls_version, waf_conn_count):
    # TLS context
    if tls_version == "TLSv1.3":
        context = ssl.SSLContext(TLS_VERSIONS[tls_version])
        context.minimum_version = ssl.TLSVersion.TLSv1_3
        context.maximum_version = ssl.TLSVersion.TLSv1_3
    else:
        context = ssl.SSLContext(TLS_VERSIONS[tls_version])

    context.load_cert_chain(certfile="adc.crt", keyfile="adc.key")

    # Initialize WAF pool
    global waf_pool
    waf_pool = WAFConnectionPool(WAF_IP, WAF_PORT, pool_size=waf_conn_count)

    # Start WAF workers
    threading.Thread(target=waf_worker, daemon=True).start()
    # threading.Thread(target=waf_response_worker, daemon=True).start()

    # Start TLS server
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server_sock:
        server_sock.bind((HOST, PORT))
        server_sock.listen()
        logger.info(f"[+] TLS server listening on {HOST}:{PORT}, TLS version {tls_version}")

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
