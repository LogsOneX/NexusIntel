import httpx

from core.targets import classify_target


metadata = {
    "name": "HTTP Header Diagnostics",
    "description": "Inspect public HTTP response headers and highlight missing browser-side security controls.",
    "category": "infrastructure",
    "target_types": ["domain", "url"],
    "tags": ["headers", "http", "security"],
    "passive": True,
    "risk": "low",
}


SECURITY_HEADERS = [
    "strict-transport-security",
    "content-security-policy",
    "x-frame-options",
    "x-content-type-options",
    "referrer-policy",
    "permissions-policy",
    "cross-origin-opener-policy",
    "cross-origin-resource-policy",
]


async def run(target: str) -> dict:
    profile = classify_target(target)
    url = profile.url or f"https://{profile.domain or profile.normalized}"

    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers={"User-Agent": "Mozilla/5.0 NexusRecon/2.0"}) as client:
        try:
            response = await client.head(url)
            if response.status_code in {405, 403}:
                response = await client.get(url)
        except Exception as exc:
            return {"status": "error", "message": f"Failed connection diagnostics check: {exc}"}

    headers = {key.lower(): value for key, value in response.headers.items()}
    present = {key: headers.get(key, "missing") for key in SECURITY_HEADERS}
    missing = [key for key, value in present.items() if value == "missing"]

    findings = {
        "url": str(response.url),
        "status_code": response.status_code,
        "server": headers.get("server", "hidden"),
        "content_type": headers.get("content-type", "missing"),
        "redirect_chain": [str(item.url) for item in response.history],
        "security_headers": present,
        "missing_security_headers": missing,
        "posture_score": max(0, 100 - (len(missing) * 12)),
    }

    return {
        "status": "success",
        "summary": f"{len(missing)} missing security header(s), score={findings['posture_score']}.",
        "data": findings,
    }
