import asyncio
from typing import Any, Dict, List

import httpx

from core.targets import classify_target, normalize_domain


metadata = {
    "name": "Flowsint-style Domain Insight",
    "description": "Passive infrastructure enrichment: RDAP, DNS, certificate transparency, mail posture, and header posture.",
    "category": "infrastructure",
    "target_types": ["domain", "url", "email"],
    "tags": ["flowsint", "domain", "dns", "rdap", "crtsh", "headers"],
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


async def _rdap(client: httpx.AsyncClient, domain: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {"registered": False}
    try:
        response = await client.get(f"https://rdap.org/domain/{domain}")
        if response.status_code != 200:
            result["error"] = f"RDAP returned {response.status_code}"
            return result
        data = response.json()
    except Exception as exc:
        result["error"] = str(exc)
        return result

    registrar = data.get("registrar")
    result["registered"] = True
    result["registrar"] = registrar.get("name") if isinstance(registrar, dict) else registrar
    result["status"] = data.get("status", [])
    result["nameservers"] = [ns.get("ldhName") for ns in data.get("nameservers", []) if isinstance(ns, dict) and ns.get("ldhName")]
    result["events"] = {
        event.get("eventAction"): event.get("eventDate")
        for event in data.get("events", [])
        if event.get("eventAction") and event.get("eventDate")
    }
    return result


async def _crtsh(client: httpx.AsyncClient, domain: str) -> List[str]:
    try:
        response = await client.get("https://crt.sh/", params={"q": f"%.{domain}", "output": "json"})
        if response.status_code != 200:
            return []
        data = response.json()
    except Exception:
        return []

    names = set()
    for item in data[:250]:
        for raw in str(item.get("name_value", "")).splitlines():
            clean = raw.strip().lower().lstrip("*.").rstrip(".")
            if clean.endswith(domain) and clean != domain:
                names.add(clean)
    return sorted(names)[:100]


async def _headers(client: httpx.AsyncClient, domain: str) -> Dict[str, str]:
    wanted = [
        "server",
        "strict-transport-security",
        "content-security-policy",
        "x-frame-options",
        "x-content-type-options",
        "referrer-policy",
    ]
    try:
        response = await client.head(f"https://{domain}", follow_redirects=True)
        return {key: response.headers.get(key, "missing") for key in wanted}
    except Exception:
        return {key: "unreachable" for key in wanted}


def _mail_posture(mx_records: List[str], txt_records: List[str], dmarc_records: List[str]) -> Dict[str, Any]:
    text = " ".join(txt_records).lower()
    dmarc_text = " ".join(dmarc_records).lower()
    return {
        "has_mx": bool(mx_records),
        "spf": "v=spf1" in text,
        "dmarc": "v=dmarc1" in dmarc_text,
        "google_workspace": any("google" in record.lower() for record in mx_records),
        "microsoft_365": any("outlook" in record.lower() or "protection.outlook" in record.lower() for record in mx_records),
    }


def _risk_summary(findings: Dict[str, Any]) -> Dict[str, Any]:
    score = 0
    reasons = []
    headers = findings.get("security_headers", {})
    mail = findings.get("mail_posture", {})

    if headers.get("strict-transport-security") in {"missing", "unreachable"}:
        score += 15
        reasons.append("missing_hsts")
    if headers.get("content-security-policy") == "missing":
        score += 10
        reasons.append("missing_csp")
    if not mail.get("spf"):
        score += 10
        reasons.append("missing_spf_hint")
    if not mail.get("dmarc"):
        score += 10
        reasons.append("missing_dmarc")
    if len(findings.get("certificate_names", [])) > 30:
        score += 8
        reasons.append("broad_certificate_surface")

    level = "low"
    if score >= 30:
        level = "medium"
    if score >= 55:
        level = "high"
    return {"risk_score": min(score, 100), "risk_level": level, "reasons": reasons}


async def run(target: str) -> dict:
    profile = classify_target(target)
    domain = profile.domain or normalize_domain(target)
    if not domain:
        return {"status": "skipped", "summary": "No domain could be extracted.", "data": {"target": target}}

    headers = {"User-Agent": "Mozilla/5.0 NexusRecon/2.0"}
    async with httpx.AsyncClient(timeout=12.0, headers=headers) as client:
        rdap_task = asyncio.create_task(_rdap(client, domain))
        dns_tasks = {
            "A": asyncio.create_task(_dns(client, domain, "A")),
            "AAAA": asyncio.create_task(_dns(client, domain, "AAAA")),
            "MX": asyncio.create_task(_dns(client, domain, "MX")),
            "NS": asyncio.create_task(_dns(client, domain, "NS")),
            "TXT": asyncio.create_task(_dns(client, domain, "TXT")),
            "DMARC": asyncio.create_task(_dns(client, f"_dmarc.{domain}", "TXT")),
            "CAA": asyncio.create_task(_dns(client, domain, "CAA")),
        }
        crt_task = asyncio.create_task(_crtsh(client, domain))
        header_task = asyncio.create_task(_headers(client, domain))

        rdap_data = await rdap_task
        dns_records = {key: await task for key, task in dns_tasks.items()}
        certificate_names = await crt_task
        security_headers = await header_task

    findings: Dict[str, Any] = {
        "domain": domain,
        "target_type": profile.kind,
        "rdap": rdap_data,
        "dns": dns_records,
        "certificate_names": certificate_names,
        "security_headers": security_headers,
        "mail_posture": _mail_posture(dns_records["MX"], dns_records["TXT"], dns_records["DMARC"]),
    }
    findings["risk"] = _risk_summary(findings)

    signal_count = sum(len(value) for value in dns_records.values()) + len(certificate_names)
    return {
        "status": "success",
        "summary": f"{signal_count} passive infrastructure signal(s), risk={findings['risk']['risk_level']}.",
        "data": findings,
    }
