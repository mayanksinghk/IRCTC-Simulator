import socket

def run_client(proxy_host='127.0.0.1', proxy_port=8000):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((proxy_host, proxy_port))
    print(f"[Client] Connected to proxy at {proxy_host}:{proxy_port}")

    while True:
        msg = input("Enter message (or 'quit'): ")
        if msg.lower() == 'quit':
            break
        s.sendall(msg.encode())
        data = s.recv(4096)
        print(f"[Client] Received: {data.decode()}")
    s.close()

if __name__ == "__main__":
    run_client()
