#!/usr/bin/env python3
import socket
import threading
import queue

HOST = '127.0.0.1'
PORT = 9000

HOST_APP = '127.0.0.1'
PORT_APP = 10000
POOL_SIZE = 1   # number of persistent connections to Application Server

# Queue of pooled connections
connection_pool = queue.Queue()

def create_app_connection():
    """Create a persistent TCP connection to the Application Server."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST_APP, PORT_APP))
    return s

def init_connection_pool():
    """Initialize pool with fixed number of connections."""
    for _ in range(POOL_SIZE):
        conn = create_app_connection()
        connection_pool.put(conn)
    print(f"[WebServer] Connection pool initialized with {POOL_SIZE} connections")

def handle_client(client_conn, addr):
    print(f"[WebServer] Connected client: {addr}")
    try:
        while True:
            data = client_conn.recv(4096)
            if not data:
                break
            print(f"[WebServer] Received from client {addr}: {data!r}")

            # Borrow a connection from the pool
            app_conn = connection_pool.get()
            try:
                app_conn.sendall(data)
                response = app_conn.recv(4096)
                client_conn.sendall(response)
            except (BrokenPipeError, ConnectionResetError):
                print("[WebServer] App connection broken, recreating...")
                app_conn.close()
                app_conn = create_app_connection()
                app_conn.sendall(data)
                response = app_conn.recv(4096)
                client_conn.sendall(response)
            finally:
                # Return connection to the pool
                connection_pool.put(app_conn)

    finally:
        client_conn.close()
        print(f"[WebServer] Closed client {addr}")

def main():
    init_connection_pool()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen(5)
    print(f"[WebServer] Listening on {HOST}:{PORT}")
    while True:
        conn, addr = sock.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
