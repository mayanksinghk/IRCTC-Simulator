#!/usr/bin/env python3
from http.server import HTTPServer, BaseHTTPRequestHandler

class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        self.wfile.write(b"Success! You reached the App Server through the entire proxy chain!\n")

print("[*] App Server starting on port 80...")
HTTPServer(('0.0.0.0', 80), SimpleHandler).serve_forever()