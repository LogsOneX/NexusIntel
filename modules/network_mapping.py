import asyncio
from typing import List

import httpx

from core.targets import classify_target, normalize_domain


metadata = {
    "name": "Passive Network Mapping",
    "description": "Map public DNS address records, authoritative nameservers, and RDAP network ownership hints.",
    "category": "infrastructure",
    "target_types": ["domain", "url", "email"],
    "tags": ["dns", "rdap", "network"],
    "passive": True,
    "risk": "low",
}


async def _dns(client: httpx.AsyncClient, domain: str, record_type: str) -> List[str]:
    try:
        response = await client.get("https://dns.google/resolve", params={"name": domain, "type": record_type})
        if response.status_code != 200:
            return []
        return [answer.get("data", "") for answer in response.json().get("Answer", []) if answer.get("data")]
    except Exception:
        return []


async def _rdap(client: httpx.AsyncClient, domain: str) -> dict:
    try:
        response = await client.get(f"https://rdap.org/domain/{domain}")
        if response.status_code != 200:
            return {"status": f"rdap_http_{response.status_code}"}
        data = response.json()
        return {
            "ldh_name": data.get("ldhName", domain),
            "status": data.get("status", []),
            "handle": data.get("handle"),
            "port_43": data.get("port43"),
            "object_class": data.get("objectClassName"),
        }
    except Exception as exc:
        return {"error": str(exc)}


async def run(target: str) -> dict:
    profile = classify_target(target)
    domain = profile.domain or normalize_domain(target)
    if not domain:
        return {"status": "skipped", "summary": "No domain candidate.", "data": {"target": target}}

    async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "Mozilla/5.0 NexusRecon/2.0"}) as client:
        tasks = {
            "a_records": asyncio.create_task(_dns(client, domain, "A")),
            "aaaa_records": asyncio.create_task(_dns(client, domain, "AAAA")),
            "ns_records": asyncio.create_task(_dns(client, domain, "NS")),
            "cname_records": asyncio.create_task(_dns(client, domain, "CNAME")),
            "rdap": asyncio.create_task(_rdap(client, domain)),
        }
        findings = {key: await task for key, task in tasks.items()}

    findings["domain"] = domain
    return {
        "status": "success",
        "summary": f"{len(findings['a_records']) + len(findings['aaaa_records'])} public address record(s).",
        "data": findings,
    }
