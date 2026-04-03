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

# ==========================
# 1. Setup Logging
# ==========================
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(levelname)s - [%(name)s] - %(message)s'
)
logger = logging.getLogger("IPS-Node")

def load_delay_pool():
    """Loads the GMM-specific delay profile for the IPS."""
    if NO_DELAY_MODE:
        logger.info("NO_DELAY_MODE is enabled. Bypassing delay pool loading.")
        return [0.0]

    try:
        with open("mininet_delays/ips_delays.json", "r") as f:
            return json.load(f)["delays_seconds"]
    except FileNotFoundError:
        logger.error("Critical: ips_delays.json not found! Falling back to default delay.")
        return [0.002] # 2ms fallback

# Load the IPS-specific GMM delay pool
DELAY_POOL = load_delay_pool()

async def pipe(reader, writer, node_direction, conn_id, is_response_side=False):
    """
    Standard TCP pipe that moves data between sockets.
    Logs activity and injects the GMM delay on the response side.
    """
    bytes_transferred = 0
    try:
        first_packet = True
        while True:
            data = await reader.read(4096)
            if not data:
                break
            
            bytes_transferred += len(data)

            # Inject GMM delay only on the first packet of the ADC's response (Downstream)
            if is_response_side and first_packet:
                if not NO_DELAY_MODE:
                    delay = random.choice(DELAY_POOL)
                    logger.debug(f"[{conn_id}] {node_direction}: Injecting GMM delay of {delay:.6f}s")
                    await asyncio.sleep(delay)
                else:
                    logger.debug(f"[{conn_id}] {node_direction}: Skipping delay (NO_DELAY_MODE active).")
                first_packet = False
            
            writer.write(data)
            await writer.drain()
            
    except Exception as e:
        logger.debug(f"[{conn_id}] Pipe broken ({node_direction}): {e}")
    finally:
        logger.debug(f"[{conn_id}] {node_direction} closed. Transferred {bytes_transferred} bytes.")
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

async def handle_client(local_reader, local_writer):
    """
    Handles transparent interception. Redirects to ADC (10.0.3.1).
    """
    conn_id = hex(random.randint(0x1000, 0xFFFF))[2:] # Short unique ID for tracking TCP streams
    client_addr = local_writer.get_extra_info('peername')
    logger.info(f"[{conn_id}] INCOMING connection intercepted from {client_addr}")
    
    start_time = time.time()

    try:
        # Connect to the ADC (The Next Hop in the CRIS DC)
        remote_reader, remote_writer = await asyncio.open_connection('10.0.3.1', 443)
        logger.debug(f"[{conn_id}] Forwarding established to ADC (10.0.3.1:443)")
        
        # Start bidirectional pipes
        # 1. User -> IPS -> ADC (Upstream: No delay)
        # 2. ADC -> IPS -> User (Downstream: GMM DELAY)
        await asyncio.gather(
            pipe(local_reader, remote_writer, "Upstream", conn_id, is_response_side=False),
            pipe(remote_reader, local_writer, "Downstream", conn_id, is_response_side=True)
        )
    except Exception as e:
        logger.error(f"[{conn_id}] Failed to connect to ADC: {e}")
        local_writer.close()
    finally:
        duration = time.time() - start_time
        logger.info(f"[{conn_id}] COMPLETED. Connection closed after {duration:.4f}s")

async def main():
    # IPS listens on 443 to intercept the TLS initiation via iptables REDIRECT
    server = await asyncio.start_server(handle_client, '0.0.0.0', 443)
    
    addr = server.sockets[0].getsockname()
    status_msg = "DISABLED" if NO_DELAY_MODE else f"ENABLED ({len(DELAY_POOL)} samples loaded)"
    logger.info(f"[*] IPS Transparent Proxy Active on {addr}")
    logger.info(f"[*] Delay Mode: {status_msg}")

    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        # 1. Force ultra-fast C-based event loop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[!] IPS Node shutting down.")