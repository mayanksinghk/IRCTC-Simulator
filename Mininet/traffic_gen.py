#!/usr/bin/env python3
import asyncio
import aiohttp
import ssl
import time

async def worker(worker_id, session, url, queue, results):
    """A worker that continuously pulls requests from the queue."""
    while True:
        try:
            # Grab a job from the queue. If empty, the worker is done.
            queue.get_nowait()
        except asyncio.QueueEmpty:
            break
            
        try:
            # We use a 10s timeout so dead packets don't stall the worker
            async with session.get(url, timeout=60) as response:
                await response.read() # Fully consume the response to free the socket
                results['success'] += 1
        except Exception:
            results['failed'] += 1
        finally:
            queue.task_done()

async def main():
    url = "https://10.0.3.1/"
    # total_requests = 1000
    total_requests = 100000
    concurrency = 50

    print(f"[*] Starting Load Test: {total_requests} packets at {concurrency} concurrency...")
    print(f"[*] Target: {url}")
    
    # 1. Ignore Self-Signed SSL Certificates
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    # 2. Hard limit the connection pool to exactly 50 sockets
    connector = aiohttp.TCPConnector(limit=concurrency, ssl=ssl_ctx)

    # 3. Create a queue and fill it with 100,000 "dummy" jobs
    queue = asyncio.Queue()
    for _ in range(total_requests):
        queue.put_nowait(1)
        
    results = {'success': 0, 'failed': 0}
    start_time = time.time()

    # 4. Spin up exactly 50 workers
    async with aiohttp.ClientSession(connector=connector) as session:
        workers = []
        for i in range(concurrency):
            task = asyncio.create_task(worker(i, session, url, queue, results))
            workers.append(task)
            
        # Wait for all workers to finish emptying the queue
        await asyncio.gather(*workers)

    # 5. Print Results
    elapsed = time.time() - start_time
    print("\n" + "="*40)
    print(f"[*] Test Finished in {elapsed:.2f} seconds")
    print(f"[*] Throughput: {total_requests / elapsed:.2f} requests/sec")
    print(f"[*] Successful (200 OK): {results['success']}")
    print(f"[*] Failed/Dropped: {results['failed']}")
    print("="*40 + "\n")

if __name__ == "__main__":
    asyncio.run(main())