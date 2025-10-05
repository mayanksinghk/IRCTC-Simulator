import socket
import threading

def handle_connection(client, next_host, next_port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.connect((next_host, next_port))

    def forward(src, dst):
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)

    # Start threads to forward data in both directions
    t1 = threading.Thread(target=forward, args=(client, server), daemon=True)
    t2 = threading.Thread(target=forward, args=(server, client), daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    client.close()
    server.close()
    print("[Proxy] Connection closed")

def run_proxy(listen_host='127.0.0.1', listen_port=8000, next_host='127.0.0.1', next_port=9000):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((listen_host, listen_port))
    s.listen(5)
    print(f"[Proxy] Listening on {listen_host}:{listen_port} -> {next_host}:{next_port}")
    while True:
        client, addr = s.accept()
        print(f"[Proxy] Accepted connection from {addr}")
        threading.Thread(target=handle_connection, args=(client, next_host, next_port), daemon=True).start()

if __name__ == "__main__":
    run_proxy()
