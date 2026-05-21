from __future__ import annotations

import asyncio
import hashlib
import json
import os
import random
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable
from urllib.parse import urlparse

import aiohttp
from bs4 import BeautifulSoup

EmitCallback = Callable[[str, dict[str, Any]], Awaitable[None] | None]

DEFAULT_USER_AGENT = os.getenv(
    "NEXUS_HTTP_USER_AGENT",
    "NexusIntel-GhostEngine/2.1 (+https://github.com/LogsOneX/NexusIntel; public-osint; read-only)",
)

NOT_FOUND_TERMS = {
    "not found",
    "page not found",
    "user not found",
    "profile not found",
    "account not found",
    "doesn't exist",
    "does not exist",
    "couldn’t find",
    "could not find",
    "no such user",
    "this account is unavailable",
    "this page isn't available",
    "sorry, this page isn't available",
    "profile is unavailable",
    "404",
}

RATE_LIMIT_CODES = {408, 425, 429, 500, 502, 503, 504}
GENERIC_TITLE_TERMS = {"sign up", "signup", "login", "log in", "register", "home", "welcome"}


def confidence_level(confidence: str) -> int:
    return {"confirmed": 95, "high": 85, "medium": 60, "low": 30, "candidate": 25}.get(confidence, 50)


@dataclass(slots=True)
class ReconFinding:
    type: str
    label: str
    value: str
    source: str
    confidence: str = "medium"
    relationship: str = "derived_signal"
    data: dict[str, Any] = field(default_factory=dict)

    def as_artifact(self) -> dict[str, Any]:
        data = {**self.data, "confidence_level": confidence_level(self.confidence)}
        return {
            "type": self.type,
            "label": self.label,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "relationship": self.relationship,
            "data": data,
        }


def normalize_domain(value: str) -> str:
    raw = value.strip().lower()
    if "://" in raw:
        raw = urlparse(raw).netloc
    return raw.split("/")[0].split(":")[0].strip(".")


def normalize_username(value: str) -> str:
    raw = value.strip()
    if raw.startswith("@"):
        raw = raw[1:]
    if "://" in raw:
        parsed = urlparse(raw)
        raw = parsed.path.rstrip("/").split("/")[-1] or parsed.netloc.split(".")[0]
    elif "/" in raw:
        raw = raw.rstrip("/").split("/")[-1]
    if raw.startswith("@"):
        raw = raw[1:]
    return re.sub(r"[^A-Za-z0-9._-]", "", raw)


def md5_lower(value: str) -> str:
    return hashlib.md5(value.strip().lower().encode("utf-8")).hexdigest()


def soup_for(html: str) -> BeautifulSoup:
    return BeautifulSoup(html[:350_000], "html.parser")


def html_title(html: str) -> str:
    soup = soup_for(html)
    title = soup.find("title")
    if title and title.get_text(strip=True):
        return title.get_text(" ", strip=True)[:240]
    og_title = soup.find("meta", attrs={"property": "og:title"}) or soup.find("meta", attrs={"name": "twitter:title"})
    if og_title and og_title.get("content"):
        return str(og_title["content"])[:240]
    return ""


def meta_content(html: str, *names: str) -> str | None:
    soup = soup_for(html)
    for name in names:
        tag = soup.find("meta", attrs={"property": name}) or soup.find("meta", attrs={"name": name})
        if tag and tag.get("content"):
            return str(tag["content"])[:500]
    return None


def public_metadata(html: str) -> dict[str, Any]:
    soup = soup_for(html)
    metadata: dict[str, Any] = {"title": html_title(html), "meta": {}, "links": {}, "data": {}}
    for key in ["og:title", "og:description", "og:image", "og:url", "twitter:title", "twitter:description", "twitter:image", "description"]:
        value = meta_content(html, key)
        if value:
            metadata["meta"][key] = value
    for rel in ["canonical", "me", "author", "alternate"]:
        tag = soup.find("link", rel=rel)
        if tag and tag.get("href"):
            metadata["links"][rel] = str(tag["href"])[:500]
    for attr in ["data-username", "data-screen-name", "data-profile-id", "data-user-id", "data-display-name"]:
        tag = soup.find(attrs={attr: True})
        if tag:
            metadata["data"][attr] = str(tag.get(attr))[:240]
    return metadata


def looks_like_not_found(text: str) -> bool:
    lowered = text[:350_000].lower()
    return any(term in lowered for term in NOT_FOUND_TERMS)


def title_is_generic(title: str) -> bool:
    clean = re.sub(r"[^a-z0-9 ]+", " ", title.lower()).strip()
    return clean in GENERIC_TITLE_TERMS or any(clean == term for term in GENERIC_TITLE_TERMS)


def text_contains_username(text: str, username: str) -> bool:
    lowered = text[:350_000].lower()
    needle = username.lower()
    compact = re.sub(r"[^a-z0-9._-]", "", needle)
    return needle in lowered or f"@{needle}" in lowered or (compact and compact in lowered)


def parse_jsonish(text: str) -> dict[str, Any] | None:
    snippet = text.strip()[:200_000]
    if not snippet or snippet[0] not in "[{":
        return None
    try:
        value = json.loads(snippet)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else {"items": value[:20] if isinstance(value, list) else value}


class AsyncHttpClient:
    def __init__(self, *, concurrency: int = 48, timeout: float = 10.0, proxy_url: str | None = None):
        self.timeout = aiohttp.ClientTimeout(total=timeout, sock_connect=min(timeout, 6), sock_read=timeout)
        self.connector = aiohttp.TCPConnector(limit=concurrency, limit_per_host=6, ttl_dns_cache=300, ssl=False)
        self.semaphore = asyncio.Semaphore(concurrency)
        self.proxy_url = proxy_url or os.getenv("NEXUS_EGRESS_PROXY") or None
        self.headers = {
            "User-Agent": DEFAULT_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/json;q=0.9,*/*;q=0.6",
            "Accept-Language": "en-US,en;q=0.8",
            "Cache-Control": "no-cache",
            "DNT": "1",
        }
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self) -> "AsyncHttpClient":
        self.session = aiohttp.ClientSession(timeout=self.timeout, connector=self.connector, headers=self.headers, raise_for_status=False)
        return self

    async def __aexit__(self, *_: object) -> None:
        if self.session:
            await self.session.close()
        await self.connector.close()

    def proxy(self) -> str | None:
        return self.proxy_url

    async def request_text(self, method: str, url: str, *, max_bytes: int = 350_000, retries: int = 2, **kwargs: Any) -> dict[str, Any]:
        if not self.session:
            raise RuntimeError("AsyncHttpClient must be used as an async context manager")
        last_error: str | None = None
        for attempt in range(retries + 1):
            async with self.semaphore:
                try:
                    async with self.session.request(method, url, proxy=self.proxy(), allow_redirects=True, **kwargs) as response:
                        raw = await response.content.read(max_bytes)
                        text = raw.decode(response.charset or "utf-8", "ignore")
                        result = {
                            "url": str(response.url),
                            "status": response.status,
                            "headers": dict(response.headers),
                            "text": text,
                            "json": parse_jsonish(text),
                            "attempt": attempt,
                        }
                        if response.status not in RATE_LIMIT_CODES:
                            return result
                        last_error = f"rate_limited_or_transient_status:{response.status}"
                except (aiohttp.ClientError, asyncio.TimeoutError) as exc:
                    last_error = str(exc)
            await asyncio.sleep(min(8.0, 0.35 * (2**attempt) + random.random() * 0.35))
        return {"url": url, "status": 0, "headers": {}, "text": "", "json": None, "error": last_error or "request_failed", "attempt": retries}


async def maybe_emit(callback: EmitCallback | None, message: str, payload: dict[str, Any] | None = None) -> None:
    if not callback:
        return
    result = callback(message, payload or {})
    if asyncio.iscoroutine(result):
        await result
