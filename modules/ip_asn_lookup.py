import asyncio
from typing import List

import httpx

from core.targets import classify_target, normalize_domain


metadata = {
    "name": "IP and ASN Intelligence",
    "description": "Resolve domains to IPs and enrich public IP ownership, CIDR, country, and network hints through RDAP.",
    "category": "infrastructure",
    "target_types": ["ip", "domain", "url", "email"],
    "tags": ["ip", "asn", "rdap", "network"],
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


async def _ip_rdap(client: httpx.AsyncClient, ip: str) -> dict:
    try:
        response = await client.get(f"https://rdap.org/ip/{ip}")
        if response.status_code != 200:
            return {"ip": ip, "status": f"rdap_http_{response.status_code}"}
        data = response.json()
    except Exception as exc:
        return {"ip": ip, "error": str(exc)}

    cidrs = data.get("cidr0_cidrs") or []
    entities = []
    for entity in data.get("entities", [])[:8]:
        entities.append(
            {
                "handle": entity.get("handle"),
                "roles": entity.get("roles", []),
                "objectClassName": entity.get("objectClassName"),
            }
        )
    return {
        "ip": ip,
        "handle": data.get("handle"),
        "name": data.get("name"),
        "type": data.get("type"),
        "country": data.get("country"),
        "start_address": data.get("startAddress"),
        "end_address": data.get("endAddress"),
        "parent_handle": data.get("parentHandle"),
        "cidrs": cidrs,
        "entities": entities,
    }


async def run(target: str) -> dict:
    profile = classify_target(target)
    ips: List[str] = []
    domain = profile.domain or None

    if profile.kind == "ip" and profile.ip:
        ips = [profile.ip]
    else:
        domain = profile.domain or normalize_domain(target)
        if not domain:
            return {"status": "skipped", "summary": "No IP or domain candidate.", "data": {"target": target}}

    async with httpx.AsyncClient(timeout=12.0, headers={"User-Agent": "Mozilla/5.0 NexusRecon/2.0"}) as client:
        if domain and not ips:
            a_task = asyncio.create_task(_dns(client, domain, "A"))
            aaaa_task = asyncio.create_task(_dns(client, domain, "AAAA"))
            ips = (await a_task) + (await aaaa_task)
        rdap = await asyncio.gather(*[_ip_rdap(client, ip) for ip in ips[:12]]) if ips else []

    network_names = sorted({item.get("name") for item in rdap if isinstance(item, dict) and item.get("name")})
    data = {
        "target": target,
        "domain": domain,
        "ip_addresses": ips,
        "networks": rdap,
        "network_names": network_names,
        "signals": [{"type": "network", "value": name} for name in network_names],
    }
    return {
        "status": "success",
        "summary": f"{len(ips)} IP address(es), {len(network_names)} network owner hint(s).",
        "data": data,
    }
