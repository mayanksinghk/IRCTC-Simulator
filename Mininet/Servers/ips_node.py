import asyncio
import json
import random
import logging
import uvloop

# ==========================
# 1. Setup Logging
# ==========================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("IPS-Node")

# Load the IPS-specific GMM delay pool
try:
    with open("mininet_delays/ips_delays.json", "r") as f:
        DELAY_POOL = json.load(f)["delays_seconds"]
except FileNotFoundError:
    logger.error("Critical: ips_delays.json not found! Falling back to default delay.")
    DELAY_POOL = [0.002] # 2ms fallback

async def pipe(reader, writer, node_direction, is_response_side=False):
    """
    Standard TCP pipe that moves data between sockets.
    Logs activity and injects the GMM delay on the response side.
    """
    try:
        first_packet = True
        while True:
            data = await reader.read(4096)
            if not data:
                break
            
            # Inject GMM delay only on the first packet of the ADC's response (Downstream)
            if is_response_side and first_packet:
                delay = random.choice(DELAY_POOL)
                # Log the specific delay for the Digital Twin audit
                logger.info(f"[*] Downstream: Injecting GMM delay of {delay:.6f}s")
                await asyncio.sleep(delay)
                first_packet = False
            
            writer.write(data)
            await writer.drain()
    except Exception as e:
        logger.debug(f"Pipe broken ({node_direction}): {e}")
    finally:
        writer.close()

async def handle_client(local_reader, local_writer):
    """
    Handles transparent interception. Redirects to ADC (10.0.3.1).
    """
    client_addr = local_writer.get_extra_info('peername')
    logger.info(f"[+] Intercepted connection from {client_addr}")

    try:
        # Connect to the ADC (The Next Hop in the CRIS DC)
        remote_reader, remote_writer = await asyncio.open_connection('10.0.3.1', 443)
        
        # Start bidirectional pipes
        # 1. User -> IPS -> ADC (Upstream: No delay)
        # 2. ADC -> IPS -> User (Downstream: GMM DELAY)
        await asyncio.gather(
            pipe(local_reader, remote_writer, "Upstream", is_response_side=False),
            pipe(remote_reader, local_writer, "Downstream", is_response_side=True)
        )
    except Exception as e:
        logger.error(f"Failed to connect to ADC: {e}")
        local_writer.close()

async def main():
    # IPS listens on 443 to intercept the TLS initiation via iptables REDIRECT
    server = await asyncio.start_server(handle_client, '0.0.0.0', 443)
    
    addr = server.sockets[0].getsockname()
    logger.info(f"[*] IPS Transparent Proxy Active on {addr}")
    logger.info(f"[*] Loaded {len(DELAY_POOL)} delay samples from GMM profile.")

    async with server:
        await server.serve_forever()

if __name__ == "__main__":
    try:
        # 1. Force ultra-fast C-based event loop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("[!] IPS Node shutting down.")