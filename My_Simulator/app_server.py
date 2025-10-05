#!/usr/bin/env python3
import socket
import threading

HOST = '127.0.0.1'
PORT = 10000

def response(data):
    return b"Echo: " + data

def handle_client(conn, addr):
    print(f"[Server] Connected: {addr}")
    try:
        while True:
            data = conn.recv(4096)
            if not data:
                break
            print(f"[Server] Received: {data!r}")
            conn.sendall(response(data))
    finally:
        conn.close()
        print(f"[Server] Closed: {addr}")

def main():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((HOST, PORT))
    sock.listen(5)
    print(f"[Server] Listening on {HOST}:{PORT}")
    while True:
        conn, addr = sock.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()
