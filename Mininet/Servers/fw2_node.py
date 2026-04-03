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
logger = logging.getLogger("BackendFW")

# Path to the GMM-derived isolated delay profile for the Backend Firewall
DELAY_PROFILE = "mininet_delays/backend_firewall_delays.json"

# The next hop in your chain (SLB or Application Server)
# Based on your emulation.py, FW2 forwards to the SLB at 10.0.4.1
NEXT_HOP_URL = "http://10.0.4.1"

def load_delay_pool():
    """Loads the Monte Carlo precomputed delay samples."""
    if NO_DELAY_MODE:
        logger.info("NO_DELAY_MODE is enabled. Bypassing delay pool loading.")
        return [0.0]

    try:
        with open(DELAY_PROFILE, 'r') as f:
            data = json.load(f)
            return data.get("delays_seconds", [0.001])
    except FileNotFoundError:
        logger.error(f"Critical: Delay profile {DELAY_PROFILE} not found! Using fallback.")
        return [0.002] # 2ms fallback delay

# Global pool for O(1) random selection
DELAY_POOL = load_delay_pool()

async def fw_handler(request):
    """
    Handles internal traffic, applies the Firewall GMM delay (if enabled),
    and forwards to the Management Zone.
    """
    start_time = time.time()
    req_id = hex(random.randint(0x1000, 0xFFFF))[2:] # Short unique ID for log tracing
    session = request.app['client_session']
    
    logger.info(f"[{req_id}] INCOMING {request.method} {request.path_qs}")

    # 1. Apply the Statistical Processing Delay
    # This represents the time taken for ACL/Stateful inspection
    if not NO_DELAY_MODE:
        delay = random.choice(DELAY_POOL)
        logger.debug(f"[{req_id}] Applying FW delay: {delay:.4f}s")
        await asyncio.sleep(delay)
    else:
        logger.debug(f"[{req_id}] Skipping FW delay (NO_DELAY_MODE active).")
    
    # 2. Construct the Forwarding URL
    target_url = f"{NEXT_HOP_URL}{request.path_qs}"
    logger.debug(f"[{req_id}] Forwarding to next hop: {target_url}")
    
    try:
        req_data = await request.read()
        # Strip 'host' to maintain internal routing integrity
        headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
        
        async with session.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=req_data,
            timeout=30 # Prevent hanging on slow downstream calls
        ) as resp:
            
            res_body = await resp.read()
            duration = time.time() - start_time
            
            logger.info(f"[{req_id}] COMPLETED {resp.status} in {duration:.4f}s")
            
            return web.Response(
                status=resp.status,
                body=res_body,
                headers=dict(resp.headers)
            )
            
    except Exception as e:
        logger.error(f"[{req_id}] Forwarding Error: {e}")
        return web.Response(status=504, text="Gateway Timeout: Backend zone unreachable.")

async def on_startup(app):
    """Initialize the high-concurrency connection pool."""
    # We use a high limit to handle the 1000-user burst
    connector = TCPConnector(limit=2000)
    app['client_session'] = ClientSession(connector=connector)
    
    status_msg = "DISABLED" if NO_DELAY_MODE else f"ENABLED ({len(DELAY_POOL)} samples loaded)"
    logger.info(f"[*] Backend Firewall Active. Delay Mode: {status_msg}")

async def on_cleanup(app):
    """Graceful cleanup of TCP sockets."""
    await app['client_session'].close()
    logger.info("[*] Backend Firewall session closed.")

def main():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    # Listen for all internal traffic
    app.router.add_route('*', '/{tail:.*}', fw_handler)
    
    # FW2 listens on Port 80
    web.run_app(app, port=80, access_log=None)

if __name__ == "__main__":
    # Force ultra-fast C-based event loop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    main()