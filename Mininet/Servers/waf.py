#!/usr/bin/env python3
import socket
import threading

# Listening on DMZ side
LISTEN_HOST = "10.0.3.2"  # WAF IP
LISTEN_PORT = 80          # Incoming port from ADC/clients

# Forwarding to Web Server
WEB_HOST = "10.0.3.3"
WEB_PORT = 80

def handle_client(client_sock, client_addr):
    print(f"[WAF] Connected to client: {client_addr}")

    # Connect to web server
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.connect((WEB_HOST, WEB_PORT))

    # Function to forward data in both directions
    def forward(src, dst, src_name, dst_name):
        try:
            while True:
                data = src.recv(4096)
                if not data:
                    break
                print(f"[WAF] {src_name} -> {dst_name}: {len(data)} bytes")
                dst.sendall(data)
        except Exception as e:
            print(f"[WAF] Forwarding error: {e}")
        finally:
            dst.close()
            src.close()

    # Start threads for bidirectional forwarding
    t1 = threading.Thread(target=forward, args=(client_sock, server_sock, "Client", "Web"))
    t2 = threading.Thread(target=forward, args=(server_sock, client_sock, "Web", "Client"))
    t1.start()
    t2.start()

def main():
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind((LISTEN_HOST, LISTEN_PORT))
    listener.listen(5)
    print(f"[WAF] Listening on {LISTEN_HOST}:{LISTEN_PORT}")

    while True:
        client_sock, client_addr = listener.accept()
        threading.Thread(target=handle_client, args=(client_sock, client_addr), daemon=True).start()

if __name__ == "__main__":
    main()