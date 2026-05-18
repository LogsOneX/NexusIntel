import asyncio
import time
from typing import Dict, List

import httpx

from core.targets import classify_target
from recon.platforms import USERNAME_PLATFORMS


metadata = {
    "name": "Sherlock-style Username Recon",
    "description": "Fast passive username enumeration across social, developer, creative, finance, and identity platforms.",
    "category": "identity",
    "target_types": ["username", "email", "url"],
    "tags": ["sherlock", "username", "profiles"],
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
    for item in found:
        category = str(item.get("category", "general"))
        category_hits[category] = category_hits.get(category, 0) + 1

    return {
        "status": "success",
        "summary": f"{len(found)} profile signal(s) found for {username}.",
        "data": {
            "query": username,
            "target_type": profile.kind,
            "scanned": len(results),
            "found_count": len(found),
            "missing_count": len(missing),
            "unknown_count": len(unknown),
            "error_count": len(errors),
            "category_hits": category_hits,
            "matches": sorted(found, key=lambda item: (-item["confidence"], item["platform"])),
            "uncertain": sorted(unknown + errors, key=lambda item: item["platform"]),
        },
    }
