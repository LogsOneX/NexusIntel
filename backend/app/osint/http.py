import asyncio
from collections.abc import Awaitable, Callable
from typing import TypeVar

import httpx

from app.config import get_settings

T = TypeVar("T")


def client_headers() -> dict[str, str]:
    return {
        "User-Agent": "NexusIntel-OSINT/1.0 (+local defensive public-source research)",
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.8",
    }


def make_client(timeout: float | None = None) -> httpx.AsyncClient:
    settings = get_settings()
    return httpx.AsyncClient(
        timeout=timeout or settings.request_timeout,
        follow_redirects=True,
        headers=client_headers(),
    )


async def bounded_gather(items: list[T], limit: int, worker: Callable[[T], Awaitable[T | None]]) -> list[T]:
    semaphore = asyncio.Semaphore(limit)

    async def run(item: T) -> T | None:
        async with semaphore:
            return await worker(item)

    results = await asyncio.gather(*(run(item) for item in items), return_exceptions=True)
    return [item for item in results if item and not isinstance(item, Exception)]
