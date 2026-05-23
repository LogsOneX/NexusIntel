from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from typing import Any

import httpx
from bs4 import BeautifulSoup

from backend.modules.evidence_quality import payload_sha256, with_quality


def _extract_reviews_from_html(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html[:500_000], "html.parser")
    text = soup.get_text(" ", strip=True)
    candidates: list[dict[str, Any]] = []
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


def _metadata(html: str) -> dict[str, Any]:
    soup = BeautifulSoup(html[:500_000], "html.parser")
    title = soup.find("title")
    og_image = soup.find("meta", attrs={"property": "og:image"})
    og_title = soup.find("meta", attrs={"property": "og:title"})
    return {
        "title": title.get_text(" ", strip=True) if title else None,
        "og_title": og_title.get("content") if og_title else None,
        "avatar_url": og_image.get("content") if og_image else None,
    }


def _gaia_from_url(url: str) -> str | None:
    match = re.search(r"/contrib/(\d+)", url)
    return match.group(1) if match else None


async def lookup_google_footprint(email: str) -> dict[str, Any]:
    """Parse only explicit public Google Maps contribution documents.

    Email alone is not treated as proof of a Google account. This resolver never returns
    synthetic profiles/reviews and never probes recovery, People, Calendar, or internal
    Google endpoints. Operators must provide an explicit public Maps contribution URL
    through NEXUS_GOOGLE_PUBLIC_PROFILE_URL for this transform to create graph pivots.
    """

    target = email.strip().lower()
    public_url = os.getenv("NEXUS_GOOGLE_PUBLIC_PROFILE_URL", "").strip()
    if not public_url:
        return with_quality({
            "email": target,
            "verified": False,
            "status": "no_public_profile_url_configured",
            "gaia_id": None,
            "display_name": None,
            "avatar_url": None,
            "reviews": [],
            "guardrail": "email_not_inferred_without_explicit_public_maps_profile_url",
        })

    if "google." not in public_url or "/maps/" not in public_url:
        return with_quality({
            "email": target,
            "verified": False,
            "status": "invalid_public_profile_url",
            "source_url": public_url,
            "reviews": [],
            "guardrail": "only_public_google_maps_profile_urls_are_accepted",
        })

    async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "NexusIntel/2.3 public-osint read-only"}) as client:
        response = await client.get(public_url)
        response.raise_for_status()
        html = response.text

    meta = _metadata(html)
    reviews = _extract_reviews_from_html(html)
    final_url = str(response.url)
    gaia_id = _gaia_from_url(final_url) or _gaia_from_url(public_url)
    verified = bool(gaia_id or reviews or meta.get("og_title") or meta.get("title"))
    return with_quality({
        "email": target,
        "verified": verified,
        "status": "verified_public_maps_document" if verified else "public_document_no_profile_indicators",
        "source": "explicit_public_google_maps_profile",
        "source_url": final_url,
        "http_status": response.status_code,
        "payload_sha256": payload_sha256(html[:500_000]),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "gaia_id": gaia_id,
        "display_name": meta.get("og_title") or meta.get("title"),
        "avatar_url": meta.get("avatar_url"),
        "reviews": reviews,
        "guardrail": "explicit_public_maps_profile_url_only",
    })
