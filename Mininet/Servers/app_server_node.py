#!/usr/bin/env python3
import asyncio
import json
import random
import logging
import uvloop
import os
import time

# --- Configuration & Environment Variables ---
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
NO_DELAY_MODE = os.getenv("NO_DELAY_MODE", "False").lower() in ("true", "1", "t", "yes")

# Configure Logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO), 
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
)
logger = logging.getLogger("AppServer-L4")

# Path to the GMM-derived isolated delay profile
DELAY_PROFILE = "mininet_delays/application_server_delays.json"

# Backend Logic (fast_app.py) IP and Port
BACKEND_HOST = '127.0.0.1'
BACKEND_PORT = 8080

def load_delay_pool():
    if NO_DELAY_MODE:
        logger.info("NO_DELAY_MODE is enabled. Bypassing delay pool loading.")
        return [0.0]

    try:
        with open(DELAY_PROFILE, 'r') as f:
            data = json.load(f)
            return data.get("delays_seconds", [0.001])
    except FileNotFoundError:
        logger.error(f"Critical: Delay profile {DELAY_PROFILE} not found! Using fallback.")
        return [0.005]

DELAY_POOL = load_delay_pool()

async def tcp_proxy_handler(local_reader, local_writer):
    """
    High-throughput Layer 4 proxy. 
    Supports HTTP Keep-Alive and prevents read-hanging via micro-timeouts.
    """
    req_id = hex(random.randint(0x1000, 0xFFFF))[2:]
    
    try:
        remote_reader, remote_writer = await asyncio.open_connection(BACKEND_HOST, BACKEND_PORT)
    except Exception as e:
        logger.error(f"[{req_id}] Backend connection failed: {e}")
        local_writer.close()
        return

    try:
        # OUTER LOOP: Allow the traffic generator to reuse the connection (Keep-Alive)
        while True:
            # 1. Wait for request
            client_data = await local_reader.read(8192)
            if not client_data:
                break # Client cleanly closed the connection

            # 2. START TIMER
            start_time = time.perf_counter()
            target_delay = 0.0 if NO_DELAY_MODE else random.choice(DELAY_POOL)

            # 3. Forward to Backend
            remote_writer.write(client_data)
            await remote_writer.drain()

            # 4. Read the initial backend response
            backend_response = await remote_reader.read(8192)
            if not backend_response:
                break # Backend closed the connection

            # 5. STOP TIMER & Apply Compensation Padding
            actual_processing_time = time.perf_counter() - start_time
            
            if not NO_DELAY_MODE:
                compensation_delay = max(0.0, target_delay - actual_processing_time)
                if compensation_delay > 0:
                    await asyncio.sleep(compensation_delay)
            
            # 6. Send the main response back to the client
            local_writer.write(backend_response)
            await local_writer.drain()

            # INNER LOOP FIX: Rapidly flush any remaining split-packets without hanging
            while True:
                try:
                    # If no more data arrives in 5ms, assume HTTP response is fully transferred
                    more_data = await asyncio.wait_for(remote_reader.read(8192), timeout=0.005)
                    if not more_data:
                        break
                    local_writer.write(more_data)
                    await local_writer.drain()
                except asyncio.TimeoutError:
                    break # Flush complete! Ready for the next request on this connection.

    except ConnectionResetError:
        pass # Normal under heavy load testing
    except Exception as e:
        logger.error(f"[{req_id}] Proxy Error: {e}")
    finally:
        local_writer.close()
        remote_writer.close()
        try:
            await local_writer.wait_closed()
        except Exception:
            pass

async def main():
    status_msg = "DISABLED" if NO_DELAY_MODE else f"ENABLED ({len(DELAY_POOL)} samples loaded)"
    logger.info(f"[*] App Server L4 Proxy ready on port 80. Delay Mode: {status_msg}")
    
    server = await asyncio.start_server(tcp_proxy_handler, '0.0.0.0', 80)
    
    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    asyncio.run(main())