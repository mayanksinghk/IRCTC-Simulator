#!/usr/bin/env python3
import asyncio
import argparse
import pandas as pd
import numpy as np
import logging
import subprocess
import ssl
import os
from aiohttp import web, ClientSession

# Suppress noisy access logs for high-throughput testing
logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger("Proxy")

def load_empirical_distribution(file_path):
    """
    Loads raw data from EITHER an isolated CSV or a raw PCAP file, 
    converts it into a 1ms bucket probability curve, and returns the weights.
    """
    if not file_path:
        logger.info("[!] No delay profile provided. Proxy will pass-through with 0ms delay.")
        return [0.0], [1.0]

    logger.info(f"[*] Calculating Probability Curve from {file_path}...")
    try:
        if file_path.endswith('.pcap'):
            # Extract HTTP response times directly from the captured packets
            logger.info("[*] Detected PCAP. Extracting 'http.time' via tshark...")
            cmd = ["tshark", "-r", file_path, "-Y", "http.response", "-T", "fields", "-e", "http.time"]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            raw_delays = []
            for line in result.stdout.split('\n'):
                if line.strip():
                    try:
                        # Sometimes tshark outputs multiple comma-separated values; grab the first
                        val = line.split(',')[0].strip()
                        raw_delays.append(float(val))
                    except ValueError:
                        pass
            raw_delays = np.array(raw_delays)
            logger.info(f"[+] Extracted {len(raw_delays)} HTTP response packets directly from PCAP.")
            
        else:
            # Assume standard isolated CSV from previous steps
            df = pd.read_csv(file_path)
            col_name = 'latency_seconds' if 'latency_seconds' in df.columns else 'HTTP_Response_Time_Seconds'
            raw_delays = df[col_name].values

        # Create the 1ms buckets (0.0 to 2.0 seconds)
        MAX_TIME = 2.0
        bins_1ms = np.arange(0, MAX_TIME + 0.001, 0.001)
        
        # Calculate the Frequencies
        counts, _ = np.histogram(raw_delays, bins=bins_1ms)
        
        # Calculate the Empirical Probabilities (Weights)
        total_samples = len(raw_delays)
        if total_samples == 0:
            logger.warning("[!] Data source is empty. Defaulting to 0ms delay.")
            return [0.0], [1.0]
            
        probabilities = counts / total_samples
        probabilities = probabilities / np.sum(probabilities)
        bucket_times = (bins_1ms[:-1] + bins_1ms[1:]) / 2
        
        logger.info(f"[+] Successfully built Probability Distribution (Loaded {total_samples} samples).")
        return bucket_times, probabilities
        
    except FileNotFoundError:
        logger.error(f"[X] File not found: {file_path}")
        exit(1)
    except Exception as e:
        logger.error(f"[X] Error processing file: {e}")
        exit(1)

async def proxy_handler(request):
    """Handles incoming requests, applies empirical delay, and forwards them."""
    app = request.app
    
    # 1. Generate a random delay using the Empirical Probability Curve
    delay = np.random.choice(app['bucket_times'], p=app['probabilities'])
    
    # 2. Asynchronously pause for the calculated processing time
    if delay > 0:
        await asyncio.sleep(delay)
        
    # 3. Construct the backend URL (Force HTTP to the internal network)
    backend_url = f"http://{app['backend_ip']}:{app['backend_port']}{request.path_qs}"
    
    # 4. Forward the request
    try:
        req_data = await request.read()
        excluded_headers = ['host', 'transfer-encoding', 'content-encoding', 'content-length']
        headers = {k: v for k, v in request.headers.items() if k.lower() not in excluded_headers}
        
        async with ClientSession() as session:
            async with session.request(request.method, backend_url, headers=headers, data=req_data) as backend_resp:
                res_body = await backend_resp.read()
                res_headers = {k: v for k, v in backend_resp.headers.items() if k.lower() not in excluded_headers}
                
                return web.Response(status=backend_resp.status, headers=res_headers, body=res_body)
    except Exception as e:
        return web.Response(status=502, text=f"Bad Gateway: Unable to reach next hop ({app['backend_ip']}:{app['backend_port']}) -> {e}")

async def start_proxy(listen_port, backend_ip, backend_port, file_path, cert_path=None, key_path=None):
    """Initializes and runs the aiohttp web server with optional TLS."""
    app = web.Application()
    
    # Load the mathematical profile into memory once at startup
    bucket_times, probabilities = load_empirical_distribution(file_path)
    
    app['bucket_times'] = bucket_times
    app['probabilities'] = probabilities
    app['backend_ip'] = backend_ip
    app['backend_port'] = backend_port
    
    app.router.add_route('*', '/{tail:.*}', proxy_handler)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    # --- TLS / HTTPS Setup ---
    ssl_context = None
    if cert_path and key_path and os.path.exists(cert_path):
        ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        ssl_context.load_cert_chain(cert_path, key_path)
        logger.info(f"[*] SSL/TLS Enabled using {cert_path}")
    
    site = web.TCPSite(runner, '0.0.0.0', listen_port, ssl_context=ssl_context)
    await site.start()
    
    logger.info(f"[*] Proxy running on port {listen_port} -> Forwarding to {backend_ip}:{backend_port}")
    await asyncio.Event().wait()

def main():
    parser = argparse.ArgumentParser(description="Empirical Delay Reverse Proxy for Mininet")
    parser.add_argument("-c", "--file", default=None, help="Path to the delay profile (.csv or .pcap)")
    parser.add_argument("-b", "--backend", required=True, help="IP address of the next hop (e.g., 10.0.3.3)")
    parser.add_argument("--bport", type=int, default=80, help="Port of the next hop (Default: 80)")
    parser.add_argument("--port", type=int, default=80, help="Listen port for this proxy (Default: 80)")
    parser.add_argument("--cert", default=None, help="Path to SSL Certificate (PEM) for HTTPS")
    parser.add_argument("--key", default=None, help="Path to SSL Private Key (PEM) for HTTPS")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(start_proxy(args.port, args.backend, args.bport, args.file, args.cert, args.key))
    except KeyboardInterrupt:
        logger.info("\n[*] Shutting down proxy.")

if __name__ == '__main__':
    main()