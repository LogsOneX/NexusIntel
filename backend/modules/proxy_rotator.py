from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Iterable

import redis


@dataclass(slots=True)
class ProxyDecision:
    proxy_url: str | None
    index: int
    source: str


class ProxyRotator:
    """Redis-backed egress proxy selector for authorized read-only collection.

    This is not a bypass engine. It centralizes approved egress endpoints so operators can
    enforce allowlists, track usage, and apply polite retry/jitter behavior consistently.
    """

    def __init__(self, redis_url: str, *, key: str = "nexus:egress:proxies") -> None:
        self.redis_url = redis_url
        self.key = key
        self.client = redis.Redis.from_url(redis_url, decode_responses=True)

    def seed_from_env(self) -> int:
        raw = os.getenv("NEXUS_PROXY_POOL", "")
        proxies = [item.strip() for item in raw.split(",") if item.strip()]
        if not proxies:
            single = os.getenv("NEXUS_EGRESS_PROXY", "").strip()
            proxies = [single] if single else []
        if proxies:
            self.client.delete(self.key)
            self.client.rpush(self.key, *proxies)
        return len(proxies)

    def seed(self, proxies: Iterable[str]) -> int:
        clean = [proxy.strip() for proxy in proxies if proxy and proxy.strip()]
        self.client.delete(self.key)
        if clean:
            self.client.rpush(self.key, *clean)
        return len(clean)

    def next(self) -> ProxyDecision:
        if self.client.llen(self.key) == 0:
            self.seed_from_env()
        proxy = self.client.lpop(self.key)
        if not proxy:
            return ProxyDecision(proxy_url=None, index=-1, source="direct")
        self.client.rpush(self.key, proxy)
        index = int(time.time() * 1000) % max(1, self.client.llen(self.key))
        return ProxyDecision(proxy_url=proxy, index=index, source="redis_pool")
