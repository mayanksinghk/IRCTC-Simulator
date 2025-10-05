import socket
import threading

def handle_client(conn, addr):
    print(f"[Server] Connection from {addr}")
    while True:
        data = conn.recv(1024)
        if not data:
            break
        print(f"[Server] Received: {data.decode()}")
        conn.sendall(b"Echo: " + data)
    conn.close()
    print(f"[Server] Connection closed: {addr}")

def run_server(host='127.0.0.1', port=9000):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((host, port))
    s.listen(5)
    print(f"[Server] Listening on {host}:{port}")
    while True:
        conn, addr = s.accept()
        threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    run_server()
