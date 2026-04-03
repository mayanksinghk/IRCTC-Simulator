#!/usr/bin/env python3
from aiohttp import web

async def handle(request):
    # Instantly returns a 200 OK without queuing
    return web.Response(text="IRCTC Backend OK\n")

app = web.Application()
# Catch all routes
app.router.add_route('*', '/{tail:.*}', handle)

if __name__ == '__main__':
    # Silence the startup logs so it doesn't clutter Mininet
    import logging
    logging.getLogger('aiohttp.access').setLevel(logging.WARNING)
    web.run_app(app, host='0.0.0.0', port=8080, print=None)