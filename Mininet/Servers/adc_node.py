#!/usr/bin/env python3
import asyncio
import json
import random
import ssl
import uvloop
import logging
import time
import os
from pathlib import Path
from aiohttp import web, ClientSession, TCPConnector

# --- Configuration & Environment Variables ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
NO_DELAY_MODE = os.getenv("NO_DELAY_MODE", "False").lower() in ("true", "1", "t", "yes")

# --- PATH SETUP (Relative to this script) ---
BASE_DIR = Path(__file__).parent.resolve()
DELAY_FILE = BASE_DIR / "mininet_delays" / "adc_delays.json"
CERT_PATH = BASE_DIR / "SSL_Keys" / "adc_cert.pem"
KEY_PATH = BASE_DIR / "SSL_Keys" / "adc_key.pem"

# --- LOGGING SETUP ---
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s',
    handlers=[
        logging.FileHandler(BASE_DIR.parent / "Logs" / "adc.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("ADC-Node")

def load_delay_pool():
    """Loads the Monte Carlo precomputed delay samples."""
    if NO_DELAY_MODE:
        logger.info("NO_DELAY_MODE is enabled. Bypassing delay pool loading.")
        return [0.0]

    try:
        with open(DELAY_FILE, "r") as f:
            data = json.load(f)
            return data.get("delays_seconds", [0.001])
    except Exception as e:
        logger.error(f"Failed to load delay pool: {e}. Defaulting to fallback.")
        return [0.002] # 2ms fallback

# --- LOAD DELAY POOL ---
DELAY_POOL = load_delay_pool()

async def adc_handler(request):
    """
    Terminates SSL, applies ADC GMM delay (if enabled), 
    and forwards HTTP traffic to the WAF.
    """
    start_time = time.time()
    req_id = hex(random.randint(0x1000, 0xFFFF))[2:] # Short unique ID for log tracing
    session = request.app['client_session']
    
    logger.info(f"[{req_id}] INCOMING {request.method} {request.path_qs}")
    
    # 1. Apply the Statistical Delay Injection
    if not NO_DELAY_MODE:
        delay = random.choice(DELAY_POOL)
        logger.debug(f"[{req_id}] Applying ADC delay: {delay:.4f}s")
        await asyncio.sleep(delay)
    else:
        logger.debug(f"[{req_id}] Skipping ADC delay (NO_DELAY_MODE active).")
    
    # 2. Forward to WAF (SSL Offloaded)
    target_url = f"http://10.0.3.2{request.path_qs}"
    logger.debug(f"[{req_id}] Forwarding to WAF: {target_url}")
    
    try:
        req_data = await request.read()
        # Strip 'host' to maintain internal routing integrity
        headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
        
        async with session.request(
            method=request.method, 
            url=target_url, 
            headers=headers, 
            data=req_data,
            timeout=60 # Extended timeout for high concurrency bursts
        ) as resp:
            
            body = await resp.read()
            duration = time.time() - start_time
            
            logger.info(f"[{req_id}] COMPLETED {resp.status} in {duration:.4f}s")
            
            return web.Response(
                status=resp.status, 
                body=body, 
                headers=dict(resp.headers)
            )
            
    except asyncio.TimeoutError:
        logger.error(f"[{req_id}] Timeout Error: WAF timed out.")
        return web.Response(status=504, text="Gateway Timeout: WAF unreachable.")
    except Exception as e:
        logger.error(f"[{req_id}] Gateway Error forwarding to {target_url}: {e}")
        return web.Response(status=502, text=f"Gateway Error: {e}")

async def on_startup(app):
    # Use a persistent connector to handle 1000+ concurrent flows
    connector = TCPConnector(limit=2000) 
    app['client_session'] = ClientSession(connector=connector)
    
    status_msg = "DISABLED" if NO_DELAY_MODE else f"ENABLED ({len(DELAY_POOL)} samples loaded)"
    logger.info(f"[*] ADC Node Active. Delay Mode: {status_msg}")

async def on_cleanup(app):
    await app['client_session'].close()
    logger.info("[*] ADC Node session closed.")

app = web.Application()
app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)
app.router.add_route('*', '/{tail:.*}', adc_handler)

# --- TLS CONTEXT SETUP ---
ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
try:
    ssl_ctx.load_cert_chain(str(CERT_PATH), str(KEY_PATH))
    logger.info(f"[*] SSL Context loaded using: {CERT_PATH.name}")
except Exception as e:
    logger.critical(f"FATAL: Could not load SSL certificates from {CERT_PATH}: {e}")
    exit(1)

if __name__ == "__main__":
    # Force ultra-fast C-based event loop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logger.info("Starting ADC Node on port 443 (HTTPS)")
    web.run_app(app, port=443, ssl_context=ssl_ctx, access_log=None)