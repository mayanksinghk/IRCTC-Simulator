#!/usr/bin/env python3
import socket
import threading
import struct
import logging

# ================= Configuration ==================
HOST = "10.0.3.3"
PORT = 7000

# Configure basic logging to console
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Get a logger instance
logger = logging.getLogger(__name__)


# Store connected WAF sockets (if you want to push to multiple WAFs)
# In simple setup, each backend thread replies on same socket

def handle_connection(conn, addr):
    logger.info(f"[+] Backend: Connection from {addr}")
    try:
        while True:
            # Read 4-byte length prefix
            length_bytes = conn.recv(4)
            if not length_bytes:
                logger.info(f"[-] Connection {addr} closed")
                break

            msg_length = struct.unpack("!I", length_bytes)[0]
            data = b""
            while len(data) < msg_length:
                chunk = conn.recv(msg_length - len(data))
                if not chunk:
                    break
                data += chunk

            if not data:
                logger.info(f"[-] Connection {addr} closed during message read")
                break

            # Decode message: expecting "client_id:message"
            full_msg = data.decode(errors="ignore")
            if ':' not in full_msg:
                logger.info(f"[!] Invalid message format from {addr}: {full_msg}")
                continue

            client_id, msg = full_msg.split(":", 1)
            logger.debug(f"[>] Backend received from client {client_id}: {msg}")

            # Generate response
            response_msg = f"{client_id}:ACK:{msg}".encode()
            logger.debug(f"Sending response message: {response_msg}")

            # Send response back to WAF (same connection)
            length_prefix = len(response_msg).to_bytes(4, byteorder='big')
            conn.sendall(length_prefix + response_msg)

    except ConnectionResetError:
        logger.info(f"[-] Connection {addr} reset by peer")
    finally:
        conn.close()


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        logger.info(f"[+] Backend server listening on {HOST}:{PORT}")

        while True:
            conn, addr = s.accept()
            threading.Thread(target=handle_connection, args=(conn, addr), daemon=True).start()


if __name__ == "__main__":
    main()
