#!/usr/bin/env python3
import asyncio
import json
import random
import logging
import uvloop
from aiohttp import web, ClientSession, TCPConnector

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BackendFW")

# Path to the GMM-derived isolated delay profile for the Backend Firewall
DELAY_PROFILE = "mininet_delays/backend_firewall_delays.json"

# The next hop in your chain (SLB or Application Server)
# Based on your emulation.py, FW2 forwards to the SLB at 10.0.4.1
NEXT_HOP_URL = "http://10.0.4.1"

def load_delay_pool():
    """Loads the Monte Carlo precomputed delay samples."""
    try:
        with open(DELAY_PROFILE, 'r') as f:
            data = json.load(f)
            return data.get("delays_seconds", [0.001])
    except FileNotFoundError:
        logger.error(f"Critical: Delay profile {DELAY_PROFILE} not found!")
        return [0.002] # 2ms fallback delay

# Global pool for O(1) random selection
DELAY_POOL = load_delay_pool()

async def fw_handler(request):
    """
    Handles internal traffic, applies the Firewall GMM delay,
    and forwards to the Management Zone.
    """
    session = request.app['client_session']
    
    # 1. Apply the Statistical Processing Delay
    # This represents the time taken for ACL/Stateful inspection
    await asyncio.sleep(random.choice(DELAY_POOL))
    
    # 2. Construct the Forwarding URL
    target_url = f"{NEXT_HOP_URL}{request.path_qs}"
    
    try:
        req_data = await request.read()
        # Strip 'host' to maintain internal routing integrity
        headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
        
        async with session.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=req_data
        ) as resp:
            
            res_body = await resp.read()
            return web.Response(
                status=resp.status,
                body=res_body,
                headers=dict(resp.headers)
            )
            
    except Exception as e:
        logger.error(f"Forwarding Error: {e}")
        return web.Response(status=504, text="Gateway Timeout: Backend zone unreachable.")

async def on_startup(app):
    """Initialize the high-concurrency connection pool."""
    # We use a high limit to handle the 1000-user burst
    connector = TCPConnector(limit=2000)
    app['client_session'] = ClientSession(connector=connector)
    logger.info(f"[*] Backend Firewall Active. Profiles loaded: {len(DELAY_POOL)}")

async def on_cleanup(app):
    """Graceful cleanup of TCP sockets."""
    await app['client_session'].close()

def main():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    # Listen for all internal traffic
    app.router.add_route('*', '/{tail:.*}', fw_handler)
    
    # FW2 listens on Port 80
    web.run_app(app, port=80, access_log=None)

if __name__ == "__main__":
    # 1. Force ultra-fast C-based event loop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    main()