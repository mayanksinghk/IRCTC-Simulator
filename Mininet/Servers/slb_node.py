#!/usr/bin/env python3
import asyncio
import logging
import uvloop
from aiohttp import web, ClientSession, TCPConnector

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SLB-PassThrough")

# The next hop in the chain: Application Server (10.0.4.2)
NEXT_HOP_URL = "http://10.0.4.2"

async def slb_handler(request):
    """
    Passes traffic directly to the Application Server without adding any 
    GMM-based processing delay.
    """
    session = request.app['client_session']
    
    # Construct the destination URL
    target_url = f"{NEXT_HOP_URL}{request.path_qs}"
    
    try:
        # Read the incoming request payload
        req_data = await request.read()
        
        # Strip 'host' to maintain internal routing consistency
        headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
        
        # Forward immediately to the Application Server
        async with session.request(
            method=request.method,
            url=target_url,
            headers=headers,
            data=req_data,
            timeout=30 
        ) as resp:
            
            res_body = await resp.read()
            return web.Response(
                status=resp.status,
                body=res_body,
                headers=dict(resp.headers)
            )
            
    except Exception as e:
        logger.error(f"SLB Forwarding Error: {e}")
        return web.Response(status=502, text="SLB Error: Management zone unreachable.")

async def on_startup(app):
    """Initialize high-concurrency connection pool for the 1000-user burst."""
    # Matches your traffic_gen.py concurrency requirements
    connector = TCPConnector(limit=2000)
    app['client_session'] = ClientSession(connector=connector)
    logger.info("[*] SLB Node Active: Operating in Pass-Through mode (0ms Delay).")

async def on_cleanup(app):
    """Graceful closure of sockets."""
    await app['client_session'].close()

def main():
    app = web.Application()
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    
    # Standard catch-all route
    app.router.add_route('*', '/{tail:.*}', slb_handler)
    
    # SLB listens on Port 80
    web.run_app(app, port=80, access_log=None)

if __name__ == "__main__":
    # 1. Force ultra-fast C-based event loop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    main()