#!/usr/bin/env python3
import socket
import threading

# Web Server IP and port
WEB_IP = "10.0.3.3"   # Web server IP
WEB_PORT = 80

def handle_waf_connection(conn, addr):
    print(f"[Web] Connected to WAF: {addr}")
    try:
        request = b""
        while True:
            data = conn.recv(4096)
            if not data:
                break
            request += data

        print(f"[Web] HTTP Request:\n{request.decode(errors='ignore')}")
        print(f"[Web] Sending response...")
        # Simple HTTP Response
        response = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 25\r\n\r\nHello from Web Server!\n"
        conn.sendall(response)

    finally:
        conn.close()
        print(f"[Web] Connection closed: {addr}")

def main():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.bind((WEB_IP, WEB_PORT))
    server_sock.listen(5)
    print(f"[Web] Listening on {WEB_IP}:{WEB_PORT}...")

    while True:
        conn, addr = server_sock.accept()
        threading.Thread(target=handle_waf_connection, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()