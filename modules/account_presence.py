import asyncio
import hashlib
from typing import Dict, List, Optional

import httpx

from core.targets import classify_target


metadata = {
    "name": "Account Presence",
    "description": "Passive account-presence hints from public profile endpoints, Gravatar, package registries, and identity hubs.",
    "category": "identity",
    "target_types": ["email", "username"],
    "tags": ["email", "account-presence", "profiles", "passive"],
    "passive": True,
    "risk": "low",
}


USERNAME_CHECKS = {
    "GitHub": {"domain": "github.com", "method": "profile", "url": "https://github.com/{username}"},
    "GitLab": {"domain": "gitlab.com", "method": "profile", "url": "https://gitlab.com/{username}"},
    "npm": {"domain": "npmjs.com", "method": "profile", "url": "https://www.npmjs.com/~{username}"},
    "PyPI": {"domain": "pypi.org", "method": "profile", "url": "https://pypi.org/user/{username}"},
    "Keybase": {"domain": "keybase.io", "method": "profile", "url": "https://keybase.io/{username}"},
    "Gravatar Username": {"domain": "gravatar.com", "method": "profile", "url": "https://gravatar.com/{username}"},
    "About.me": {"domain": "about.me", "method": "profile", "url": "https://about.me/{username}"},
    "Linktree": {"domain": "linktr.ee", "method": "profile", "url": "https://linktr.ee/{username}"},
    "Bio.link": {"domain": "bio.link", "method": "profile", "url": "https://bio.link/{username}"},
    "ProductHunt": {"domain": "producthunt.com", "method": "profile", "url": "https://producthunt.com/@{username}"},
    "Medium": {"domain": "medium.com", "method": "profile", "url": "https://medium.com/@{username}"},
}


async def _probe_username(client: httpx.AsyncClient, service: str, config: dict, username: str) -> dict:
    url = config["url"].format(username=username)
    try:
        response = await client.get(url, follow_redirects=True)
        rate_limited = response.status_code == 429
        if response.status_code in {200, 301, 302, 303, 403} and "not found" not in response.text[:80000].lower():
            status, confidence = "present", 0.72 if response.status_code == 200 else 0.55
        elif response.status_code in {404, 410}:
            status, confidence = "absent", 0.90
        else:
            status, confidence = "unknown", 0.30
        return _presence_record(service, config["domain"], config["method"], status, rate_limited, confidence, url, response.status_code)
    except Exception as exc:
        return _presence_record(service, config["domain"], config["method"], "error", False, 0.0, url, None, {"error": str(exc)})


async def _probe_gravatar_email(client: httpx.AsyncClient, email: str) -> Optional[dict]:
    digest = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    url = f"https://en.gravatar.com/{digest}.json"
    try:
        response = await client.get(url, follow_redirects=True)
        if response.status_code == 200:
            data = response.json()
            entry = data.get("entry", [{}])[0]
            return {
                "name": "Gravatar Email Hash",
                "service": "Gravatar Email Hash",
                "domain": "gravatar.com",
                "method": "email_hash",
                "rateLimit": False,
                "exists": True,
                "url": entry.get("profileUrl") or f"https://gravatar.com/{digest}",
                "status": "present",
                "status_code": response.status_code,
                "confidence": 0.88,
                "emailrecovery": None,
                "phoneNumber": None,
                "others": {"evidence": "public gravatar hash profile"},
            }
        if response.status_code == 404:
            return {
                "name": "Gravatar Email Hash",
                "service": "Gravatar Email Hash",
                "domain": "gravatar.com",
                "method": "email_hash",
                "rateLimit": False,
                "exists": False,
                "url": f"https://gravatar.com/{digest}",
                "status": "absent",
                "status_code": response.status_code,
                "confidence": 0.80,
                "emailrecovery": None,
                "phoneNumber": None,
                "others": None,
            }
    except Exception as exc:
        return {
            "name": "Gravatar Email Hash",
            "service": "Gravatar Email Hash",
            "domain": "gravatar.com",
            "method": "email_hash",
            "rateLimit": False,
            "exists": None,
            "url": f"https://gravatar.com/{digest}",
            "status": "error",
            "status_code": None,
            "confidence": 0.0,
            "emailrecovery": None,
            "phoneNumber": None,
            "others": {"error": str(exc)},
        }
    return None


async def run(target: str) -> dict:
    profile = classify_target(target)
    usernames = profile.candidate_usernames
    identity = usernames[0] if usernames else profile.normalized

    findings: List[dict] = []
    limits = httpx.Limits(max_connections=16, max_keepalive_connections=8)
    headers = {"User-Agent": "Mozilla/5.0 NexusRecon/2.0"}
    async with httpx.AsyncClient(timeout=10.0, headers=headers, limits=limits) as client:
        tasks = []
        if profile.email:
            tasks.append(_probe_gravatar_email(client, profile.email))
        if usernames:
            tasks.extend(_probe_username(client, service, config, usernames[0]) for service, config in USERNAME_CHECKS.items())

        for coro in asyncio.as_completed(tasks):
            item = await coro
            if item:
                findings.append(item)

    present = [item for item in findings if item.get("exists") is True]
    absent = [item for item in findings if item.get("exists") is False]
    uncertain = [item for item in findings if item.get("status") in {"unknown", "error"}]

    return {
        "status": "success",
        "summary": f"{len(present)} passive account-presence hint(s) for {identity}.",
        "data": {
            "identity": identity,
            "target_type": profile.kind,
            "present_count": len(present),
            "absent_count": len(absent),
            "uncertain_count": len(uncertain),
            "schema": "nexus_account_presence_v1",
            "results": sorted(findings, key=lambda item: item["name"]),
            "present": sorted(present, key=lambda item: (-item.get("confidence", 0), item["service"])),
            "uncertain": sorted(uncertain, key=lambda item: item["service"]),
        },
    }


def _presence_record(
    name: str,
    domain: str,
    method: str,
    status: str,
    rate_limited: bool,
    confidence: float,
    url: str,
    status_code: int | None,
    others: dict | None = None,
) -> dict:
    exists = True if status == "present" else False if status == "absent" else None
    return {
        "name": name,
        "service": name,
        "domain": domain,
        "method": method,
        "rateLimit": rate_limited,
        "exists": exists,
        "emailrecovery": None,
        "phoneNumber": None,
        "others": others,
        "url": url,
        "status": status,
        "status_code": status_code,
        "confidence": confidence,
    }
