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

# Configure Logging for audit reports
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO), 
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
)
logger = logging.getLogger("WAF-Node")

# Path to the GMM-derived isolated delay profile for the WAF
# This represents the overhead of Layer 7 inspection rules.
DELAY_PROFILE = "mininet_delays/waf_delays.json"

# The next hop in the chain: Web Server (10.0.3.3)
NEXT_HOP_URL = "http://10.0.3.3"

def load_delay_pool():
    """Loads the Monte Carlo precomputed delay samples from your GMM model."""
    if NO_DELAY_MODE:
        logger.info("NO_DELAY_MODE is enabled. Bypassing delay pool loading.")
        return [0.0]

    try:
        with open(DELAY_PROFILE, 'r') as f:
            data = json.load(f)
            return data.get("delays_seconds", [0.001])
    except FileNotFoundError:
        logger.error(f"Critical: WAF Delay profile {DELAY_PROFILE} not found! Using fallback.")
        return [0.003] # 3ms fallback safety delay

# Global pool for O(1) random selection during high-concurrency bursts
DELAY_POOL = load_delay_pool()

async def waf_handler(request):
    """
    Interacts with incoming traffic from ADC, applies WAF GMM delay (if enabled),
    and forwards clean traffic to the Web Server.
    """
    start_time = time.time()
    req_id = hex(random.randint(0x1000, 0xFFFF))[2:] # Short unique ID for log tracing
    session = request.app['client_session']
    
    logger.info(f"[{req_id}] INCOMING {request.method} {request.path_qs}")

    # 1. Apply the Isolated Processing Delay
    # This simulates the time taken to run regex and signature checks on the HTTP body.
    if not NO_DELAY_MODE:
        delay = random.choice(DELAY_POOL)
        logger.debug(f"[{req_id}] Applying WAF inspection delay: {delay:.4f}s")
        await asyncio.sleep(delay)
    else:
        logger.debug(f"[{req_id}] Skipping WAF inspection delay (NO_DELAY_MODE active).")
    
    # 2. Reconstruct the URL for the Web Server
    target_url = f"{NEXT_HOP_URL}{request.path_qs}"
    logger.debug(f"[{req_id}] Forwarding to next hop: {target_url}")
    
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
            duration = time.time() - start_time
            
            logger.info(f"[{req_id}] COMPLETED {resp.status} in {duration:.4f}s")
            
            return web.Response(
                status=resp.status,
                body=res_body,
                headers=dict(resp.headers)
            )
            
    except asyncio.TimeoutError:
        logger.error(f"[{req_id}] Timeout Error: Web Server timed out.")
        return web.Response(status=504, text="WAF Error: Web Server timed out.")
    except Exception as e:
        logger.error(f"[{req_id}] WAF Forwarding Error: {e}")
        return web.Response(status=502, text="WAF Error: Internal Network Path Failure.")

async def on_startup(app):
    """Initialize a persistent, high-capacity connection pool."""
    # Matches the 1000-user concurrency limit
    connector = TCPConnector(limit=2000)
    app['client_session'] = ClientSession(connector=connector)
    
    status_msg = "DISABLED" if NO_DELAY_MODE else f"ENABLED ({len(DELAY_POOL)} samples loaded)"
    logger.info(f"[*] WAF Node Active. Delay Mode: {status_msg}")

async def on_cleanup(app):
    """Graceful closure of all backend sockets."""
    await app['client_session'].close()
    logger.info("[*] WAF Node session closed.")

def main():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    # Catch-all route to proxy any incoming URL path
    app.router.add_route('*', '/{tail:.*}', waf_handler)
    
    # WAF listens on standard HTTP Port 80
    web.run_app(app, port=80, access_log=None)

if __name__ == "__main__":
    # Force ultra-fast C-based event loop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    main()