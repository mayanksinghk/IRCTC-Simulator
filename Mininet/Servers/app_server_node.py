#!/usr/bin/env python3
import asyncio
import json
import random
import logging
import uvloop
import os
import time
from aiohttp import web, ClientSession, TCPConnector

# --- Configuration & Environment Variables ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
NO_DELAY_MODE = os.getenv("NO_DELAY_MODE", "False").lower() in ("true", "1", "t", "yes")

# Configure Logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO), 
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
)
logger = logging.getLogger("AppServer")

# Path to the GMM-derived isolated delay profile
DELAY_PROFILE = "mininet_delays/application_server_delays.json"

# The local address where your 'fast_app.py' business logic is listening
BACKEND_LOGIC_URL = "http://127.0.0.1:8080"

def load_delay_pool():
    """Loads the Monte Carlo precomputed delay samples."""
    if NO_DELAY_MODE:
        logger.info("NO_DELAY_MODE is enabled. Bypassing delay pool loading.")
        return [0.0]

    try:
        with open(DELAY_PROFILE, 'r') as f:
            data = json.load(f)
            return data.get("delays_seconds", [0.001]) # Default 1ms if empty
    except FileNotFoundError:
        logger.error(f"Critical: Delay profile {DELAY_PROFILE} not found! Using fallback.")
        return [0.005] # Fallback safety delay

# Global pool for O(1) random selection
DELAY_POOL = load_delay_pool()

async def app_handler(request):
    """
    Handles incoming traffic from the network, applies GMM delay (if enabled), 
    and calls the local business logic.
    """
    start_time = time.time()
    req_id = hex(random.randint(0x1000, 0xFFFF))[2:] # Short unique ID for log tracing
    session = request.app['client_session']
    
    logger.info(f"[{req_id}] INCOMING {request.method} {request.path_qs}")

    # 1. Apply the Isolated Processing Delay (The Digital Twin "Thinking" time)
    if not NO_DELAY_MODE:
        delay = random.choice(DELAY_POOL)
        logger.debug(f"[{req_id}] Applying GMM delay: {delay:.4f}s")
        await asyncio.sleep(delay)
    else:
        logger.debug(f"[{req_id}] Skipping delay (NO_DELAY_MODE active).")
    
    # 2. Forward the request to the actual backend logic (fast_app.py)
    target_url = f"{BACKEND_LOGIC_URL}{request.path_qs}"
    logger.debug(f"[{req_id}] Forwarding to backend: {target_url}")
    
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
            duration = time.time() - start_time
            
            logger.info(f"[{req_id}] COMPLETED {backend_resp.status} in {duration:.4f}s")
            
            return web.Response(
                status=backend_resp.status,
                body=res_body,
                headers=dict(backend_resp.headers)
            )
            
    except Exception as e:
        logger.error(f"[{req_id}] Backend Error: {e}")
        return web.Response(status=502, text="App Server Error: Logic layer unreachable.")

async def on_startup(app):
    """Initialize a high-concurrency connection pool to the local backend."""
    connector = TCPConnector(limit=1500)
    app['client_session'] = ClientSession(connector=connector)
    
    status_msg = "DISABLED" if NO_DELAY_MODE else f"ENABLED ({len(DELAY_POOL)} samples loaded)"
    logger.info(f"[*] App Server ready. Delay Mode: {status_msg}")

async def on_cleanup(app):
    """Graceful shutdown of the session."""
    await app['client_session'].close()
    logger.info("[*] App Server session closed.")

def main():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    # Catch-all route to handle any API endpoint
    app.router.add_route('*', '/{tail:.*}', app_handler)
    
    # Listen on port 80 (or whatever port your FW2/SLB targets)
    web.run_app(app, port=80, access_log=None)

if __name__ == "__main__":
    # Force ultra-fast C-based event loop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    main()