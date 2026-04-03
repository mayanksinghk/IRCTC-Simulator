import asyncio
import json
import random
import ssl
import uvloop
from aiohttp import web, ClientSession, TCPConnector

# Pre-load GMM pool for O(1) lookup speed
with open("mininet_delays/adc_delays.json", "r") as f:
    DELAY_POOL = json.load(f)["delays_seconds"]

async def adc_handler(request):
    session = request.app['client_session']
    
    # 1. Statistical Delay Injection
    await asyncio.sleep(random.choice(DELAY_POOL))
    
    # 2. Forward to WAF (SSL Offloaded)
    target_url = f"http://10.0.3.2{request.path_qs}"
    
    try:
        req_data = await request.read()
        headers = {k: v for k, v in request.headers.items() if k.lower() != 'host'}
        
        async with session.request(request.method, target_url, headers=headers, data=req_data) as resp:
            body = await resp.read()
            return web.Response(status=resp.status, body=body, headers=dict(resp.headers))
    except Exception as e:
        return web.Response(status=502, text=f"Gateway Error: {e}")

async def on_startup(app):
    # Use a persistent connector to handle 1000+ concurrent flows
    connector = TCPConnector(limit=2000) 
    app['client_session'] = ClientSession(connector=connector)

async def on_cleanup(app):
    await app['client_session'].close()

app = web.Application()
app.on_startup.append(on_startup)
app.on_cleanup.append(on_cleanup)
app.router.add_route('*', '/{tail:.*}', adc_handler)

# TLS Context for Port 443
ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
ssl_ctx.load_cert_chain("/home/mayank/Desktop/IRCTC/IRCTC-Simulator/docs/Mininet/Servers/SSL_Keys/adc_cert.pem", "/home/mayank/Desktop/IRCTC/IRCTC-Simulator/docs/Mininet/Servers/SSL_Keys/adc_key.pem")

if __name__ == "__main__":
    # 1. Force ultra-fast C-based event loop
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    web.run_app(app, port=443, ssl_context=ssl_ctx)