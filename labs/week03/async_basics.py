import asyncio
import random
import time

URLS = [f"https://example.com/{i}" for i in range(1, 21)]
SLOW_URLS = [f"https://example.com/{i}" for i in range(5, 11)]
MAX_IN_FLIGHT = 5
TIMEOUT = 2.0

in_flight = 0
peak_in_flight = 0


async def fetch(url: str, limit: asyncio.Semaphore) -> str:
    global in_flight, peak_in_flight
    async with limit:
        in_flight += 1
        peak_in_flight = max(peak_in_flight, in_flight)
        try:
            delay = 5.0 if url in SLOW_URLS else random.uniform(0.5, 1.5)
            async with asyncio.timeout(TIMEOUT):
                await asyncio.sleep(delay)  # Simulate network delay
                return f"{url}: ok"
        except TimeoutError:
            raise

        except asyncio.CancelledError:
            print(f"Cancelled {url}")
            raise
        finally:
            in_flight -= 1


async def main() -> None:
    limit = asyncio.Semaphore(MAX_IN_FLIGHT)
    start = time.perf_counter()

    results = await asyncio.gather(
        *(fetch(url, limit) for url in URLS), return_exceptions=True
    )

    ok = [r for r in results if isinstance(r, str)]
    failed = [r for r in results if isinstance(r, BaseException)]
    print(
        f"{len(ok)} succeeded, {len(failed)} failed: {[type(e).__name__ for e in failed]}"
    )
    print(f"peak in flight: {peak_in_flight}")
    print(f"total time: {time.perf_counter() - start:.1f}s")

    task = asyncio.create_task(fetch("https://example.com/cancel", limit))
    await asyncio.sleep(0.1)  # Let the task start
    task.cancel()  # Cancel the task

    try:
        await task
    except asyncio.CancelledError:
        print("Task was cancelled successfully")


if __name__ == "__main__":
    asyncio.run(main())
