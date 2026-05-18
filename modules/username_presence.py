import asyncio
import re
import time
from typing import Dict, List
from urllib.parse import urljoin, urlparse

import httpx

from core.targets import classify_target
from recon.platforms import USERNAME_PLATFORMS


metadata = {
    "name": "Username Presence",
    "description": "Fast passive username enumeration across social, developer, creative, finance, and identity platforms.",
    "category": "identity",
    "target_types": ["username", "email", "url"],
    "tags": ["username", "profiles", "social", "developer"],
    "passive": True,
    "risk": "low",
}


async def _probe(client: httpx.AsyncClient, name: str, config: Dict[str, object], username: str) -> dict:
    url = str(config["url"]).format(username=username)
    negative = [str(item).lower() for item in config.get("negative", [])]
    start = time.time()

    try:
        response = await client.get(url, follow_redirects=True)
        elapsed = round(time.time() - start, 2)
        body = response.text[:120000].lower()

        title, links = _extract_profile_context(response.url, response.text)

        if response.status_code in {404, 410}:
            status, confidence, evidence = "missing", 0.95, f"HTTP {response.status_code}"
        elif response.status_code == 429:
            status, confidence, evidence = "unknown", 0.25, "rate limited"
        elif response.status_code in {200, 301, 302, 303, 403}:
            marker = next((item for item in negative if item and item in body), None)
            if marker:
                status, confidence, evidence = "missing", 0.72, f"negative marker: {marker}"
            else:
                status = "found"
                confidence = 0.82 if response.status_code == 200 else 0.62
                evidence = f"HTTP {response.status_code}"
        else:
            status, confidence, evidence = "unknown", 0.35, f"HTTP {response.status_code}"

        return {
            "platform": name,
            "category": config.get("type", "general"),
            "url": url,
            "status": status,
            "status_code": response.status_code,
            "confidence": confidence,
            "response_time": elapsed,
            "evidence": evidence,
            "title": title,
            "links": links if status == "found" else [],
            "tags": config.get("tags", []),
        }
    except Exception as exc:
        return {
            "platform": name,
            "category": config.get("type", "general"),
            "url": url,
            "status": "error",
            "status_code": None,
            "confidence": 0.0,
            "response_time": round(time.time() - start, 2),
            "evidence": str(exc),
            "title": None,
            "links": [],
            "tags": config.get("tags", []),
        }


async def run(target: str) -> dict:
    profile = classify_target(target)
    usernames = profile.candidate_usernames
    if not usernames:
        return {
            "status": "skipped",
            "summary": "No username candidate could be extracted from target.",
            "data": {"target": target, "target_type": profile.kind},
        }

    username = usernames[0]
    results: List[dict] = []
    limits = httpx.Limits(max_connections=35, max_keepalive_connections=12)
    headers = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) NexusRecon/2.0"}

    async with httpx.AsyncClient(timeout=12.0, headers=headers, limits=limits) as client:
        tasks = [_probe(client, name, config, username) for name, config in USERNAME_PLATFORMS.items()]
        for coro in asyncio.as_completed(tasks):
            results.append(await coro)

    found = [item for item in results if item["status"] == "found"]
    missing = [item for item in results if item["status"] == "missing"]
    unknown = [item for item in results if item["status"] == "unknown"]
    errors = [item for item in results if item["status"] == "error"]

    category_hits: Dict[str, int] = {}
    domains: Dict[str, int] = {}
    extracted_links: List[dict] = []
    for item in found:
        category = str(item.get("category", "general"))
        category_hits[category] = category_hits.get(category, 0) + 1
        for link in item.get("links", [])[:8]:
            domain = str(link.get("domain", ""))
            if domain:
                domains[domain] = domains.get(domain, 0) + 1
            extracted_links.append(
                {
                    "platform": item["platform"],
                    "url": link.get("url"),
                    "domain": domain,
                    "label": link.get("label"),
                }
            )

    footprint_score = min(100, int(len(found) * 6 + len(category_hits) * 8 + len(domains) * 2))
    confidence_bands = {
        "high": len([item for item in found if item.get("confidence", 0) >= 0.80]),
        "medium": len([item for item in found if 0.55 <= item.get("confidence", 0) < 0.80]),
        "low": len([item for item in found if item.get("confidence", 0) < 0.55]),
    }

    return {
        "status": "success",
        "summary": f"{len(found)} profile signal(s), footprint={footprint_score}/100 for {username}.",
        "data": {
            "query": username,
            "target_type": profile.kind,
            "scanned": len(results),
            "found_count": len(found),
            "missing_count": len(missing),
            "unknown_count": len(unknown),
            "error_count": len(errors),
            "category_hits": category_hits,
            "confidence_bands": confidence_bands,
            "footprint_score": footprint_score,
            "top_link_domains": sorted(domains.items(), key=lambda item: (-item[1], item[0]))[:20],
            "links": extracted_links[:120],
            "matches": sorted(found, key=lambda item: (-item["confidence"], item["platform"])),
            "uncertain": sorted(unknown + errors, key=lambda item: item["platform"]),
        },
    }


def _extract_profile_context(final_url: httpx.URL, body: str) -> tuple[str | None, list[dict]]:
    head = body[:160000]
    title = None
    match = re.search(r"<title[^>]*>(.*?)</title>", head, re.IGNORECASE | re.DOTALL)
    if match:
        title = re.sub(r"\s+", " ", match.group(1)).strip()[:120]

    base_host = urlparse(str(final_url)).netloc.lower().removeprefix("www.")
    links = []
    seen = set()
    for href, label in re.findall(r"<a[^>]+href=[\"']([^\"']+)[\"'][^>]*>(.*?)</a>", head, re.IGNORECASE | re.DOTALL):
        url = urljoin(str(final_url), href.strip())
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            continue
        host = parsed.netloc.lower().removeprefix("www.")
        if host == base_host or url in seen:
            continue
        seen.add(url)
        clean_label = re.sub(r"<[^>]+>", " ", label)
        clean_label = re.sub(r"\s+", " ", clean_label).strip()[:80]
        links.append({"url": url, "domain": host, "label": clean_label})
        if len(links) >= 12:
            break
    return title, links
