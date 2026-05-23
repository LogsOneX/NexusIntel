from __future__ import annotations

import os
from typing import Any

import httpx

from backend.modules.evidence_quality import with_quality


async def invoke_serverless(payload: dict[str, Any]) -> dict[str, Any]:
    endpoint = os.getenv("NEXUS_SERVERLESS_INVOKER_URL", "").strip()
    token = os.getenv("NEXUS_SERVERLESS_INVOKER_TOKEN", "").strip()
    if not endpoint:
        return with_quality({
            "verified": False,
            "status": "disabled",
            "provider": "none",
            "reason": "NEXUS_SERVERLESS_INVOKER_URL is not configured; no invocation was made.",
        })
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers={"User-Agent": "NexusIntel/2.3 authorized-public-osint"}) as client:
        response = await client.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
    if isinstance(data, dict):
        data.setdefault("verified", True)
        data.setdefault("status", "verified_serverless_invocation")
        data.setdefault("source_url", endpoint)
        return with_quality(data)
    return with_quality({"verified": True, "status": "verified_serverless_invocation", "source_url": endpoint, "result": data})
