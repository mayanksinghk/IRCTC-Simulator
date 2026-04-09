#!/usr/bin/env python3
import asyncio
import aiohttp
import time
import logging
from tqdm import tqdm

# ==========================================
# 1. LOGGING CONFIGURATION
# ==========================================
# We log to a file so it doesn't break the visual progress bar in the terminal
logging.basicConfig(
    filename='traffic_gen.log',
    filemode='w', # Overwrite log file on each run
    level=logging.INFO,
    format='%(asctime)s - [%(levelname)s] - %(message)s'
)
logger = logging.getLogger("TrafficGen")

async def worker(session, url, queue, results, pbar):
    """Pulls requests from the queue and executes them concurrently."""
    while True:
        try:
            queue.get_nowait()
        except asyncio.QueueEmpty:
            break
            
        try:
            async with session.get(url, timeout=10) as response:
                await response.read()
                if response.status == 200:
                    results['success'] += 1
                else:
                    results['failed'] += 1
        except Exception:
            results['failed'] += 1
        finally:
            queue.task_done()
            
            # Update the progress bar
            pbar.update(1)
            
            # Log every 1000 requests
            completed = pbar.n
            if completed % 1000 == 0:
                logger.info(
                    f"Progress: {completed} requests completed. "
                    f"Success: {results['success']} | Failed: {results['failed']}"
                )

async def main():
    url = "http://10.0.0.2:80/"
    total_requests = 100000  # Adjust for stress testing
    concurrency = 50         # Number of simultaneous connections

    print(f"[*] Starting Load Test: {total_requests} requests at {concurrency} concurrency...")
    print(f"[*] Target: {url}")
    logger.info(f"Started load test against {url} with {total_requests} requests (Concurrency: {concurrency})")
    
    connector = aiohttp.TCPConnector(limit=concurrency)
    queue = asyncio.Queue()
    for _ in range(total_requests):
        queue.put_nowait(1)
        
    results = {'success': 0, 'failed': 0}
    start_time = time.time()

    # ==========================================
    # 2. INITIALIZE PROGRESS BAR
    # ==========================================
    # unit_scale dynamically changes requests to 'k' (e.g., 10k)
    # smoothing=0.1 gives a more accurate current requests/sec speed
    pbar = tqdm(
        total=total_requests, 
        desc="Traffic Gen", 
        unit="req", 
        colour='green',
        smoothing=0.1 
    )

    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for _ in range(concurrency):
            # Pass the pbar into the worker so it can update it
            task = asyncio.create_task(worker(session, url, queue, results, pbar))
            tasks.append(task)
        await asyncio.gather(*tasks)

    pbar.close() # Clean up the progress bar once done

    elapsed = time.time() - start_time
    
    # Final console output
    print("\n" + "="*40)
    print(f"[*] Test Finished in {elapsed:.2f} seconds")
    print(f"[*] Throughput: {total_requests / elapsed:.2f} requests/sec")
    print(f"[*] Successful (200 OK): {results['success']}")
    print(f"[*] Failed/Dropped: {results['failed']}")
    print("="*40 + "\n")
    
    # Final log output
    logger.info(f"Test Complete. Time: {elapsed:.2f}s | Throughput: {total_requests/elapsed:.2f} req/s")
    logger.info(f"Final Stats - Success: {results['success']} | Failed: {results['failed']}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Test interrupted by user.")
        logging.warning("Test interrupted by user via KeyboardInterrupt.")