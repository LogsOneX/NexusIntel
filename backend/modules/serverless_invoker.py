from __future__ import annotations

import os
from typing import Any

import httpx


async def invoke_serverless(payload: dict[str, Any]) -> dict[str, Any]:
    if os.getenv("NEXUS_ENV") == "development":
        return {"dry_run": True, "provider": "development", "payload": payload, "status": "simulated"}
    endpoint = os.getenv("NEXUS_SERVERLESS_INVOKER_URL", "").strip()
    token = os.getenv("NEXUS_SERVERLESS_INVOKER_TOKEN", "").strip()
    if not endpoint:
        return {"dry_run": True, "provider": "disabled", "reason": "NEXUS_SERVERLESS_INVOKER_URL not configured"}
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(endpoint, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
