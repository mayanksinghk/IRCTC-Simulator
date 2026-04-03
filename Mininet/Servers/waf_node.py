#!/usr/bin/env python3
import asyncio
import json
import random
import logging
import uvloop
from aiohttp import web, ClientSession, TCPConnector

# Configure Logging for audit reports
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WAF-Node")

# Path to the GMM-derived isolated delay profile for the WAF
# This represents the overhead of Layer 7 inspection rules.
DELAY_PROFILE = "mininet_delays/waf_delays.json"

# The next hop in the chain: Web Server (10.0.3.3)
NEXT_HOP_URL = "http://10.0.3.3"

def load_delay_pool():
    """Loads the Monte Carlo precomputed delay samples from your GMM model."""
    try:
        with open(DELAY_PROFILE, 'r') as f:
            data = json.load(f)
            return data.get("delays_seconds", [0.001])
    except FileNotFoundError:
        logger.error(f"Critical: WAF Delay profile {DELAY_PROFILE} not found!")
        return [0.003] # 3ms fallback safety delay

# Global pool for O(1) random selection during high-concurrency bursts
DELAY_POOL = load_delay_pool()

async def waf_handler(request):
    """
    Interacts with incoming traffic from ADC, applies WAF GMM delay,
    and forwards clean traffic to the Web Server.
    """
    session = request.app['client_session']
    
    # 1. Apply the Isolated Processing Delay
    # This simulates the time taken to run regex and signature checks on the HTTP body.
    await asyncio.sleep(random.choice(DELAY_POOL))
    
    # 2. Reconstruct the URL for the Web Server
    target_url = f"{NEXT_HOP_URL}{request.path_qs}"
    
    try:
        # Read the payload (important for inspecting POST requests in a real WAF)
        req_data = await request.read()
        
        # Strip 'host' header to ensure compatibility with the Web Server's listener
        headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
        
        async with session.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=req_data,
            timeout=60 # Extended timeout for heavy 100k request bursts
        ) as resp:
            
            res_body = await resp.read()
            return web.Response(
                status=resp.status,
                body=res_body,
                headers=dict(resp.headers)
            )
            
    except asyncio.TimeoutError:
        return web.Response(status=504, text="WAF Error: Web Server timed out.")
    except Exception as e:
        logger.error(f"WAF Forwarding Error: {e}")
        return web.Response(status=502, text="WAF Error: Internal Network Path Failure.")

async def on_startup(app):
    """Initialize a persistent, high-capacity connection pool."""
    # Matches the 1000-user concurrency limit
    connector = TCPConnector(limit=2000)
    app['client_session'] = ClientSession(connector=connector)
    logger.info(f"[*] WAF Node Active. Profile loaded with {len(DELAY_POOL)} samples.")

async def on_cleanup(app):
    """Graceful closure of all backend sockets."""
    await app['client_session'].close()

def main():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    # Catch-all route to proxy any incoming URL path
    app.router.add_route('*', '/{tail:.*}', waf_handler)
    
    # WAF listens on standard HTTP Port 80
    web.run_app(app, port=80, access_log=None)

if __name__ == "__main__":
    # 1. Force ultra-fast C-based event loop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    main()