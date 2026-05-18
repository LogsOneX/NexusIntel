import re
from html.parser import HTMLParser
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import httpx

from core.targets import classify_target


metadata = {
    "name": "Website Surface Mapper",
    "description": "Passive website-to-links, page metadata, emails, and tracker hints inspired by graph investigation enrichers.",
    "category": "infrastructure",
    "target_types": ["domain", "url"],
    "tags": ["website", "links", "trackers", "surface"],
    "passive": True,
    "risk": "low",
}


TRACKER_PATTERNS = {
    "Google Analytics": "google-analytics.com",
    "Google Tag Manager": "googletagmanager.com",
    "Meta Pixel": "connect.facebook.net",
    "Hotjar": "hotjar.com",
    "Cloudflare": "cloudflareinsights.com",
    "Microsoft Clarity": "clarity.ms",
    "Segment": "segment.com",
    "Sentry": "sentry.io",
}


class SurfaceParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.in_title = False
        self.title_parts: List[str] = []
        self.meta: Dict[str, str] = {}
        self.links: List[str] = []
        self.assets: List[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key.lower(): value or "" for key, value in attrs}
        if tag == "title":
            self.in_title = True
        if tag == "meta":
            name = (values.get("name") or values.get("property") or "").lower()
            if name in {"description", "og:title", "og:description", "twitter:title", "twitter:description"}:
                self.meta[name] = values.get("content", "")
        if tag == "a" and values.get("href"):
            self.links.append(urljoin(self.base_url, values["href"]))
        if tag in {"script", "img", "link"}:
            src = values.get("src") or values.get("href")
            if src:
                self.assets.append(urljoin(self.base_url, src))

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data.strip())

    @property
    def title(self) -> str:
        return " ".join(part for part in self.title_parts if part).strip()


async def run(target: str) -> dict:
    profile = classify_target(target)
    url = profile.url or f"https://{profile.domain or profile.normalized}"
    domain = profile.domain or urlparse(url).netloc.lower()
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    try:
        async with httpx.AsyncClient(timeout=12.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 NexusRecon/2.0"}) as client:
            response = await client.get(url)
    except Exception as exc:
        return {"status": "error", "message": f"Website surface lookup failed: {exc}"}

    content_type = response.headers.get("content-type", "")
    body = response.text[:350000]
    parser = SurfaceParser(str(response.url))
    if "html" in content_type.lower() or "<html" in body.lower():
        parser.feed(body)

    internal_links = []
    external_links = []
    seen = set()
    for link in parser.links:
        parsed = urlparse(link)
        if not parsed.scheme.startswith("http"):
            continue
        clean = link.split("#", 1)[0]
        if clean in seen:
            continue
        seen.add(clean)
        item = {"url": clean, "host": parsed.netloc.lower(), "kind": "internal" if parsed.netloc.lower().endswith(domain) else "external"}
        if item["kind"] == "internal":
            internal_links.append(item)
        else:
            external_links.append(item)

    trackers = []
    scan_text = " ".join([body, " ".join(parser.assets)]).lower()
    for name, marker in TRACKER_PATTERNS.items():
        if marker in scan_text:
            trackers.append({"name": name, "marker": marker})

    emails = sorted(set(re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", body)))[:30]
    text_sample = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", body)).strip()[:500]

    data = {
        "url": str(response.url),
        "domain": domain,
        "status_code": response.status_code,
        "content_type": content_type,
        "title": parser.title,
        "meta": parser.meta,
        "internal_links": internal_links[:80],
        "external_links": external_links[:80],
        "emails": emails,
        "trackers": trackers,
        "asset_count": len(parser.assets),
        "text_sample": text_sample,
    }
    signals = len(internal_links[:80]) + len(external_links[:80]) + len(emails) + len(trackers)
    return {
        "status": "success",
        "summary": f"{signals} website surface signal(s), {len(trackers)} tracker hint(s).",
        "data": data,
    }
