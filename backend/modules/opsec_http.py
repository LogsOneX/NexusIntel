from __future__ import annotations

import asyncio
import random
from dataclasses import dataclass
from typing import Any

import aiohttp

from .proxy_rotator import ProxyRotator


@dataclass(slots=True)
class HttpResult:
    url: str
    status: int
    text: str
    headers: dict[str, str]
    proxy_source: str
    attempts: int


class OpsecHttpClient:
    """Polite async HTTP client with jitter/backoff and optional approved proxy pool."""

    def __init__(self, *, proxy_rotator: ProxyRotator | None = None, timeout: float = 14.0) -> None:
        self.proxy_rotator = proxy_rotator
        self.timeout = aiohttp.ClientTimeout(total=timeout, sock_connect=min(timeout, 6), sock_read=timeout)
        self.headers = {
            "User-Agent": "NexusIntel/2.2 authorized-public-osint read-only",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.6",
            "Accept-Language": "en-US,en;q=0.8",
            "DNT": "1",
        }

    async def request_text(self, method: str, url: str, *, attempts: int = 3, **kwargs: Any) -> HttpResult:
        last_exc: Exception | None = None
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            for attempt in range(1, attempts + 1):
                await asyncio.sleep(random.uniform(1.2, 4.7))
                decision = self.proxy_rotator.next() if self.proxy_rotator else None
                try:
                    async with session.request(method.upper(), url, proxy=decision.proxy_url if decision else None, **kwargs) as response:
                        text = await response.text(errors="ignore")
                        if response.status in {408, 425, 429, 500, 502, 503, 504} and attempt < attempts:
                            await asyncio.sleep(min(25.0, (2 ** attempt) + random.uniform(0.2, 1.4)))
                            continue
                        return HttpResult(
                            url=str(response.url),
                            status=response.status,
                            text=text,
                            headers={key: value for key, value in response.headers.items()},
                            proxy_source=decision.source if decision else "direct",
                            attempts=attempt,
                        )
                except Exception as exc:  # noqa: BLE001 - network edge normalization
                    last_exc = exc
                    if attempt < attempts:
                        await asyncio.sleep(min(25.0, (2 ** attempt) + random.uniform(0.2, 1.4)))
                        continue
            raise RuntimeError(f"HTTP collection failed for {url}: {last_exc}")
