#!/usr/bin/env python3
import socket
import ssl
import threading
import os 

# ADC configuration
ADC_LISTEN_IP = "10.0.3.1"
ADC_LISTEN_PORT = 443
WAF_IP = "10.0.3.2"   # waf1 IP in your topology
WAF_PORT = 80

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CERT_FILE = os.path.join(BASE_DIR, "adc.crt")
KEY_FILE = os.path.join(BASE_DIR, "adc.key")


def handle_client(connstream, addr):
    print(f"[+] New TLS connection from {addr}")
    try:
        # Connect to WAF as plain TCP
        waf_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        waf_sock.connect((WAF_IP, WAF_PORT))
        print(f"[+] Connected to WAF at {WAF_IP}:{WAF_PORT}")

        # Bidirectional forwarding between TLS client <-> WAF
        def forward(src, dst):
            while True:
                print(f"[.] Forwarding data from {src.getpeername()} to {dst.getpeername()}")
                data = src.recv(4096)
                if not data:
                    break
                dst.sendall(data)

        t1 = threading.Thread(target=forward, args=(connstream, waf_sock))
        t2 = threading.Thread(target=forward, args=(waf_sock, connstream))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
    except Exception as e:
        print(f"[!] Error: {e}")
    finally:
        connstream.close()
        waf_sock.close()
        print(f"[-] Connection {addr} closed")


def main():
    # Create listening TCP socket
    bindsock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    bindsock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    bindsock.bind((ADC_LISTEN_IP, ADC_LISTEN_PORT))
    bindsock.listen(5)

    # Wrap with SSL
    # os.system("ls")
    # exit()
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)

    print(f"[*] ADC listening on {ADC_LISTEN_IP}:{ADC_LISTEN_PORT}, forwarding to {WAF_IP}:{WAF_PORT}")

    while True:
        newsock, addr = bindsock.accept()
        try:
            connstream = context.wrap_socket(newsock, server_side=True)
            threading.Thread(target=handle_client, args=(connstream, addr)).start()
        except ssl.SSLError as e:
            print(f"[!] TLS error with {addr}: {e}")
            newsock.close()


if __name__ == "__main__":
    main()