#!/usr/bin/env python3
import asyncio
import json
import random
import logging
import os
import time
from aiohttp import web

# Attempt to load uvloop for maximum performance
try:
    import uvloop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ImportError:
    pass

# --- Configuration & Environment Variables ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
NO_DELAY_MODE = os.getenv("NO_DELAY_MODE", "False").lower() in ("true", "1", "t", "yes")

# Configure Logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO), 
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
)
logger = logging.getLogger("AppLayer-Server")

DELAY_PROFILE = "delay.json"

# ==========================================
# 1. DELAY LOGIC
# ==========================================
def load_delay_pool():
    if NO_DELAY_MODE:
        logger.info("NO_DELAY_MODE is enabled. Bypassing delay pool loading.")
        return [0.0]

    try:
        with open(DELAY_PROFILE, 'r') as f:
            data = json.load(f)
            return data.get("delays_seconds", [0.001])
    except FileNotFoundError:
        logger.error(f"Critical: Delay profile {DELAY_PROFILE} not found! Using fallback of 5ms.")
        return [0.005]

DELAY_POOL = load_delay_pool()

# ==========================================
# 2. HTTP REQUEST HANDLER
# ==========================================
async def handle_request(request):
    """Handles the HTTP request at the application layer and applies simulated delay."""
    
    # 1. Start Timer
    start_time = time.perf_counter()
    target_delay = 0.0 if NO_DELAY_MODE else random.choice(DELAY_POOL)

    # 2. Calculate compensation delay
    actual_processing_time = time.perf_counter() - start_time
    if not NO_DELAY_MODE:
        compensation_delay = max(0.0, target_delay - actual_processing_time)
        if compensation_delay > 0:
            await asyncio.sleep(compensation_delay)
    
    # 3. Return a clean HTTP Response
    return web.Response(text="200 OK - Application Layer Server Response!\n")

# ==========================================
# 3. MASTER RUNNER
# ==========================================
def main():
    status_msg = "DISABLED" if NO_DELAY_MODE else f"ENABLED ({len(DELAY_POOL)} samples loaded)"
    logger.info(f"[*] Starting Application Layer Server on port 80. Delay Mode: {status_msg}")
    
    app = web.Application()
    
    # Route all GET requests to our handler. 
    # You can change '{tail:.*}' to '/' if you only want to serve the root path.
    app.router.add_get('/{tail:.*}', handle_request)
    
    # We set access_log to None to prevent massive console spam during load testing
    web.run_app(app, host='0.0.0.0', port=80, access_log=None)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Shutting down Application Server.")