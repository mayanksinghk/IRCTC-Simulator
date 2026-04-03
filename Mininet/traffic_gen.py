#!/usr/bin/env python3
import asyncio
import aiohttp
import ssl
import time
from tqdm import tqdm  # Ensure you run: pip install tqdm

async def worker(session, url, queue, pbar, results):
    """A worker that continuously pulls requests from the queue."""
    while True:
        try:
            # Grab a job from the queue. If empty, the worker is done.
            queue.get_nowait()
        except asyncio.QueueEmpty:
            break
            
        try:
            # 60s timeout to account for the deep GMM proxy chain overhead
            async with session.get(url, timeout=60) as response:
                await response.read() # Fully consume to free the socket
                if response.status == 200:
                    results['success'] += 1
                else:
                    results['failed'] += 1
        except Exception:
            results['failed'] += 1
        finally:
            pbar.update(1) # Increment the visual progress bar
            queue.task_done()

async def main():
    # Target the ADC/IPS entry point
    url = "https://10.0.3.1/"
    total_requests = 1000  # Change to 100,000 for final stress test
    concurrency = 50       # Matches your standard IRCTC burst profile

    print(f"[*] Starting Load Test: {total_requests} packets at {concurrency} concurrency...")
    print(f"[*] Target: {url}")
    
    # 1. SSL Configuration (Bypass for self-signed ADC certs)
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    # 2. Connector with concurrency limit
    connector = aiohttp.TCPConnector(limit=concurrency, ssl=ssl_ctx)

    # 3. Initialize Queue and Results
    queue = asyncio.Queue()
    for _ in range(total_requests):
        queue.put_nowait(1)
        
    results = {'success': 0, 'failed': 0}
    start_time = time.time()

    # 4. Initialize Progress Bar
    pbar = tqdm(total=total_requests, desc="IRCTC Load Test", unit="req", colour='green')

    # 5. Execute Workers
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for _ in range(concurrency):
            task = asyncio.create_task(worker(session, url, queue, pbar, results))
            tasks.append(task)
            
        await asyncio.gather(*tasks)

    pbar.close() # Cleanly close the bar before printing results

    # 6. Print Results
    elapsed = time.time() - start_time
    print("\n" + "="*40)
    print(f"[*] Test Finished in {elapsed:.2f} seconds")
    print(f"[*] Throughput: {total_requests / elapsed:.2f} requests/sec")
    print(f"[*] Successful (200 OK): {results['success']}")
    print(f"[*] Failed/Dropped: {results['failed']}")
    print("="*40 + "\n")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[!] Test interrupted by user.")