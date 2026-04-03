#!/usr/bin/env python3
import asyncio
import json
import random
import logging
import uvloop
from aiohttp import web, ClientSession, TCPConnector

# Configure Logging for performance auditing
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Web-Server")

# Path to the GMM-derived isolated delay profile for the Web Server
# This represents the overhead of the web service (e.g., Nginx/Apache) 
# parsing headers and managing internal request buffers.
DELAY_PROFILE = "mininet_delays/web_server_delays.json"

# The next hop in the chain: Backend Firewall (FW2) at 10.0.3.253
NEXT_HOP_URL = "http://10.0.3.253"

def load_delay_pool():
    """Loads the Monte Carlo precomputed delay samples."""
    try:
        with open(DELAY_PROFILE, 'r') as f:
            data = json.load(f)
            return data.get("delays_seconds", [0.001])
    except FileNotFoundError:
        logger.error(f"Critical: Web Server Delay profile {DELAY_PROFILE} not found!")
        return [0.001] # 1ms fallback delay

# Global pool for O(1) random selection during the 100,000 request burst
DELAY_POOL = load_delay_pool()

async def web_handler(request):
    """
    Handles traffic from the WAF, applies Web Server GMM delay,
    and forwards the request toward the Management Zone via FW2.
    """
    session = request.app['client_session']
    
    # 1. Apply the Isolated Processing Delay
    # This simulates the time the web server takes to process the request 
    # before sending it to the backend firewall.
    await asyncio.sleep(random.choice(DELAY_POOL))
    
    # 2. Construct the URL for the next hop (FW2)
    target_url = f"{NEXT_HOP_URL}{request.path_qs}"
    
    try:
        # Read the payload
        req_data = await request.read()
        
        # Strip 'host' to maintain internal routing integrity
        headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
        
        async with session.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=req_data,
            timeout=60
        ) as resp:
            
            res_body = await resp.read()
            return web.Response(
                status=resp.status,
                body=res_body,
                headers=dict(resp.headers)
            )
            
    except Exception as e:
        logger.error(f"Web Server Forwarding Error: {e}")
        return web.Response(status=502, text="Web Server Error: Internal Gateway Failure.")

async def on_startup(app):
    """Initialize a persistent connection pool for high concurrency."""
    # Matches the 1000-user concurrency limit in your traffic_gen.py
    connector = TCPConnector(limit=2000)
    app['client_session'] = ClientSession(connector=connector)
    logger.info(f"[*] Web Server Node Active. Profile loaded: {len(DELAY_POOL)} samples.")

async def on_cleanup(app):
    """Graceful closure of backend sockets to prevent TIME_WAIT saturation."""
    await app['client_session'].close()

def main():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    # Catch-all route to proxy any incoming URL path
    app.router.add_route('*', '/{tail:.*}', web_handler)
    
    # The Web Server listens on standard HTTP Port 80
    web.run_app(app, port=80, access_log=None)

if __name__ == "__main__":
    # 1. Force ultra-fast C-based event loop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    main()