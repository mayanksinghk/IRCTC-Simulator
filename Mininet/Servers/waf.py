#!/usr/bin/env python3
import socket
import threading
import struct
import queue
import logging

# Configure basic logging to console
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Get a logger instance
logger = logging.getLogger(__name__)

# ================= Configuration ==================
HOST = "10.0.3.2"          # WAF listens here
PORT = 8080                 # WAF port

BACKEND_IP = "10.0.3.3"     # Backend server IP
BACKEND_PORT = 7000         # Backend server port
BACKEND_POOL_SIZE = 10      # Persistent backend connections

FORWARD_TO_BACKEND = True
# ==================================================

# Queue for messages to be sent to backend
backend_queue = queue.Queue()

# Mapping client_id -> TLS server connection
client_map = {}

# ================= Backend Connection Pool ==================
class BackendConnectionPool:
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
            s.setblocking(False)  # Non-blocking to read responses
            self.connections.append(s)
        logger.info(f"[+] Initialized backend pool with {self.pool_size} connections")

    def send(self, msg: bytes):
        """Send message to backend using round-robin"""
        with self.lock:
            conn = self.connections[self.next_conn]
            self.next_conn = (self.next_conn + 1) % self.pool_size
        length_prefix = len(msg).to_bytes(4, byteorder='big')
        conn.sendall(length_prefix + msg)

# ================= Backend Worker ==================
def backend_worker():
    """Thread to forward messages from queue to backend"""
    while True:
        msg = backend_queue.get()
        if msg is None:
            break
        backend_pool.send(msg)

# ================= Backend Response Worker ==================
def backend_response_worker():
    """Read responses from backend pool and send to correct TLS server connection"""
    while True:
        for conn in backend_pool.connections:
            try:
                length_bytes = conn.recv(4)
                if not length_bytes:
                    continue
                msg_length = struct.unpack("!I", length_bytes)[0]
                data = b""
                while len(data) < msg_length:
                    chunk = conn.recv(msg_length - len(data))
                    if not chunk:
                        break
                    data += chunk
                if not data:
                    continue

                # Expect format: client_id:response_message
                msg = data.decode(errors="ignore")
                logger.debug(f"[<] Backend response: {msg}")
                if ':' not in msg:
                    continue

                client_id, response_msg = msg.split(":", 1)
                logger.debug(f"Routing response to client_id {client_id}")
                if client_id in client_map:
                    conn = client_map[client_id]
                    logger.debug(f"Sending to TLS client: {response_msg}, conn={conn}")
                    length_prefix = len(msg).to_bytes(4, byteorder='big')
                    conn.sendall(length_prefix + response_msg.encode())
            except BlockingIOError:
                continue
            except Exception as e:
                logger.info(f"[!] Backend response error: {e}")

# ================= WAF Connection Handler ==================
def handle_waf_connection(conn, addr):
    logger.info(f"[+] WAF: Connection from {addr}")
    try:
        while True:
            # Read length-prefixed message
            length_bytes = conn.recv(4)
            if not length_bytes:
                break
            msg_length = struct.unpack("!I", length_bytes)[0]
            data = b""
            while len(data) < msg_length:
                chunk = conn.recv(msg_length - len(data))
                if not chunk:
                    break
                data += chunk
            if not data:
                break

            msg = data.decode(errors="ignore")
            logger.debug(f"[>] WAF received from {addr}: {msg}")

            # Extract client_id
            if ':' not in msg:
                logger.info(f"[!] Invalid message format from {addr}: {msg}")
                continue
            client_id, actual_msg = msg.split(":", 1)

            # Store mapping
            if client_id not in client_map:
                client_map[client_id] = conn

            # Forward to backend
            if FORWARD_TO_BACKEND:
                backend_queue.put(data)

    except ConnectionResetError:
        logger.info(f"[-] Connection {addr} reset by peer")
    finally:
        conn.close()

# ================= Main WAF Server ==================
def main():
    global backend_pool
    backend_pool = BackendConnectionPool(BACKEND_IP, BACKEND_PORT, BACKEND_POOL_SIZE)

    # Start worker threads
    threading.Thread(target=backend_worker, daemon=True).start()
    threading.Thread(target=backend_response_worker, daemon=True).start()

    # Start WAF listener
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        logger.info(f"[+] WAF server listening on {HOST}:{PORT}")

        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_waf_connection, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
