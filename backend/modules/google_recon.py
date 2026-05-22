from __future__ import annotations

import os
import re
from typing import Any

import httpx
from bs4 import BeautifulSoup


def _dummy(email: str) -> dict[str, Any]:
    return {
        "email": email,
        "dry_run": True,
        "gaia_id": "100000000000000000000",
        "display_name": "NexusIntel Dry Run",
        "avatar_url": "https://lh3.googleusercontent.com/a/default-user",
        "reviews": [
            {
                "place_name": "Dry Run Operations Center",
                "address": "Jakarta, Indonesia",
                "coordinates": {"lat": -6.2, "lon": 106.8},
                "rating": 5,
                "timestamp": "development",
                "snippet": "Synthetic review used for local graph testing.",
            },
            {
                "place_name": "Public Source Lab",
                "address": "Singapore",
                "coordinates": {"lat": 1.3521, "lon": 103.8198},
                "rating": 4,
                "timestamp": "development",
                "snippet": "Dry-run location footprint; no external Google request was made.",
            },
        ],
        "guardrail": "development_dry_run_no_external_google_request",
    }


def _extract_reviews_from_html(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html[:500_000], "html.parser")
    text = soup.get_text(" ", strip=True)
    candidates = []
    for match in re.finditer(r"([A-Z][A-Za-z0-9 &'.,-]{4,80})\s+(?:Rated|rating)\s+(\d(?:\.\d)?)", text):
        candidates.append({
            "place_name": match.group(1).strip(),
            "address": "",
            "coordinates": {},
            "rating": float(match.group(2)),
            "timestamp": "public_html",
            "snippet": text[max(0, match.start() - 80): match.end() + 160][:260],
        })
    return candidates[:25]


async def lookup_google_footprint(email: str) -> dict[str, Any]:
    """Safe Google footprint resolver.

    Development mode returns deterministic dummy graph data. Production mode does not probe
    internal Google account recovery, People API hints, or invite endpoints by email. If an
    operator provides an explicit public Maps profile URL through NEXUS_GOOGLE_PUBLIC_PROFILE_URL,
    this function parses that public document only.
    """

    target = email.strip().lower()
    if os.getenv("NEXUS_ENV") == "development":
        return _dummy(target)

    public_url = os.getenv("NEXUS_GOOGLE_PUBLIC_PROFILE_URL", "").strip()
    if not public_url:
        return {
            "email": target,
            "dry_run": False,
            "gaia_id": None,
            "display_name": None,
            "avatar_url": None,
            "reviews": [],
            "guardrail": "no_internal_google_probe_public_profile_url_not_configured",
        }

    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "NexusIntel/2.2 public-osint read-only"}) as client:
        response = await client.get(public_url)
        response.raise_for_status()
        html = response.text
    return {
        "email": target,
        "dry_run": False,
        "gaia_id": public_url.rstrip('/').split('/')[-2] if '/contrib/' in public_url else None,
        "display_name": None,
        "avatar_url": None,
        "reviews": _extract_reviews_from_html(html),
        "guardrail": "explicit_public_maps_profile_url_only",
    }
