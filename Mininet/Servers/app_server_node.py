#!/usr/bin/env python3
import asyncio
import json
import random
import logging
import uvloop
from aiohttp import web, ClientSession, TCPConnector

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AppServer")

# Path to the GMM-derived isolated delay profile
# For a terminal node, this represents the full internal processing lag.
DELAY_PROFILE = "mininet_delays/application_server_delays.json"

# The local address where your 'fast_app.py' business logic is listening
BACKEND_LOGIC_URL = "http://127.0.0.1:8080"

def load_delay_pool():
    """Loads the Monte Carlo precomputed delay samples."""
    try:
        with open(DELAY_PROFILE, 'r') as f:
            data = json.load(f)
            return data.get("delays_seconds", [0.001]) # Default 1ms if empty
    except FileNotFoundError:
        logger.error(f"Critical: Delay profile {DELAY_PROFILE} not found!")
        return [0.005] # Fallback safety delay

# Global pool for O(1) random selection
DELAY_POOL = load_delay_pool()

async def app_handler(request):
    """
    Handles incoming traffic from the network, applies GMM delay, 
    and calls the local business logic.
    """
    session = request.app['client_session']
    
    # 1. Apply the Isolated Processing Delay (The Digital Twin "Thinking" time)
    delay = random.choice(DELAY_POOL)
    await asyncio.sleep(delay)
    
    # 2. Forward the request to the actual backend logic (fast_app.py)
    # We maintain the path and query string (e.g., /book?train=12301)
    target_url = f"{BACKEND_LOGIC_URL}{request.path_qs}"
    
    try:
        req_data = await request.read()
        # Strip 'host' to avoid loops or header mismatches
        headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
        
        async with session.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=req_data,
            timeout=30 # Prevent hanging on slow backend calls
        ) as backend_resp:
            
            res_body = await backend_resp.read()
            return web.Response(
                status=backend_resp.status,
                body=res_body,
                headers=dict(backend_resp.headers)
            )
            
    except Exception as e:
        logger.error(f"Backend Error: {e}")
        return web.Response(status=502, text="App Server Error: Logic layer unreachable.")

async def on_startup(app):
    """Initialize a high-concurrency connection pool to the local backend."""
    # Since it's talking to localhost, we don't need 2000 connections, 
    # but we keep it high to match your 1000-user burst capacity.
    connector = TCPConnector(limit=1500)
    app['client_session'] = ClientSession(connector=connector)
    logger.info(f"[*] App Server ready. Loaded {len(DELAY_POOL)} delay samples.")

async def on_cleanup(app):
    """Graceful shutdown of the session."""
    await app['client_session'].close()

def main():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    # Catch-all route to handle any API endpoint defined in fast_app.py
    app.router.add_route('*', '/{tail:.*}', app_handler)
    
    # The App Server listens on the standard HTTP port 80 
    # (or whatever port your FW2/SLB targets)
    web.run_app(app, port=80, access_log=None)

if __name__ == "__main__":
    # 1. Force ultra-fast C-based event loop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    main()