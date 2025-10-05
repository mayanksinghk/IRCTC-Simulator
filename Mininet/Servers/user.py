#!/usr/bin/env python3
import socket
import ssl
from scapy.all import *
import random

# ADC address and port
ADC_IP = "10.0.3.1"   # change to adc1 IP from user1's perspective
ADC_PORT = 443


def random_http_payload():   
    # Simple random HTTP GET request
    http_methods = ["GET", "POST", "HEAD"]
    paths = ["/", "/index.html", "/login", "/api/data"]
    method = random.choice(http_methods)
    path = random.choice(paths)
    host = ADC_IP
    http_payload = f"{method} {path} HTTP/1.1\r\nHost: {host}\r\n\r\n"
    
    return http_payload


def main():
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # skip cert verification for testing

    # Connect TCP
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ADC_IP, ADC_PORT))

    # Wrap with TLS
    conn = context.wrap_socket(sock, server_hostname="adc1")

    for i in range(10):
        payload = random_http_payload()
        print(f"=== Sending HTTP Request {i+1} ===")
        print(payload)
        conn.sendall(payload.encode())
        
        # Receive response
        response = b""
        while True:
            data = conn.recv(4096)
            if not data:
                break
            response += data

        print("=== HTTP Response ===")
        print(response.decode(errors="ignore"))
        time.sleep(1)  # wait before sending next request

    conn.close()

if __name__ == "__main__":
    main()