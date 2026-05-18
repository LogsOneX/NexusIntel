from urllib.parse import quote_plus

import httpx

from core.targets import classify_target


metadata = {
    "name": "Account Pivot Enrichment",
    "description": "Email, domain, and username pivots across public account, workspace, and developer signals.",
    "category": "identity",
    "target_types": ["email", "username", "domain"],
    "tags": ["account", "google", "github", "gitlab", "public-api"],
    "passive": True,
    "risk": "low",
}


async def _dns(client: httpx.AsyncClient, domain: str, record_type: str) -> list[str]:
    try:
        response = await client.get("https://dns.google/resolve", params={"name": domain, "type": record_type})
        if response.status_code != 200:
            return []
        return [answer.get("data", "") for answer in response.json().get("Answer", []) if answer.get("data")]
    except Exception:
        return []


async def _github_profile(client: httpx.AsyncClient, username: str) -> dict:
    result = {}
    try:
        response = await client.get(f"https://api.github.com/users/{username}")
        if response.status_code == 200:
            data = response.json()
            result["profile"] = {
                "login": data.get("login"),
                "name": data.get("name"),
                "company": data.get("company"),
                "blog": data.get("blog"),
                "location": data.get("location"),
                "public_repos": data.get("public_repos"),
                "followers": data.get("followers"),
                "created_at": data.get("created_at"),
                "html_url": data.get("html_url"),
                "avatar_url": data.get("avatar_url"),
            }
        else:
            result["profile_status"] = response.status_code
    except Exception as exc:
        result["profile_error"] = str(exc)

    try:
        response = await client.get(f"https://api.github.com/users/{username}/events/public", params={"per_page": 10})
        if response.status_code == 200:
            events = response.json()
            result["recent_event_types"] = sorted({event.get("type") for event in events if event.get("type")})
    except Exception:
        result["recent_event_types"] = []
    return result


async def _gitlab_matches(client: httpx.AsyncClient, username: str) -> list[dict]:
    try:
        response = await client.get("https://gitlab.com/api/v4/users", params={"search": username, "per_page": 5})
        if response.status_code != 200:
            return []
        return [
            {
                "username": item.get("username"),
                "name": item.get("name"),
                "web_url": item.get("web_url"),
                "avatar_url": item.get("avatar_url"),
            }
            for item in response.json()
        ]
    except Exception:
        return []


async def run(target: str) -> dict:
    profile = classify_target(target)
    subject = profile.normalized
    username = profile.candidate_usernames[0] if profile.candidate_usernames else None
    domain = profile.domain

    findings = {
        "target": subject,
        "target_type": profile.kind,
        "provider": None,
        "google_workspace_signals": [],
        "public_search_pivots": [],
    }

    headers = {"User-Agent": "Mozilla/5.0 NexusRecon/2.0"}
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        if domain:
            mx_records = await _dns(client, domain, "MX")
            txt_records = await _dns(client, domain, "TXT")
            findings["mx_records"] = mx_records
            findings["txt_records"] = txt_records[:20]
            if any("google" in record.lower() for record in mx_records):
                findings["provider"] = "Google / Google Workspace"
                findings["google_workspace_signals"].append("google_mx")
            if any("google-site-verification" in record.lower() for record in txt_records):
                findings["google_workspace_signals"].append("google_site_verification_txt")

        if profile.email and profile.email.endswith(("@gmail.com", "@googlemail.com")):
            findings["provider"] = "Google consumer account domain"
            findings["google_workspace_signals"].append("gmail_domain")

        if username:
            findings["github"] = await _github_profile(client, username)
            findings["gitlab_matches"] = await _gitlab_matches(client, username)

    if profile.email:
        encoded = quote_plus(f'"{profile.email}"')
        findings["public_search_pivots"].extend(
            [
                f"https://www.google.com/search?q={encoded}",
                f"https://github.com/search?q={encoded}&type=code",
            ]
        )
    if username:
        encoded_user = quote_plus(username)
        findings["public_search_pivots"].extend(
            [
                f"https://www.google.com/search?q={encoded_user}",
                f"https://github.com/search?q={encoded_user}&type=users",
            ]
        )

    signals = len(findings.get("google_workspace_signals", []))
    if findings.get("github", {}).get("profile"):
        signals += 1
    signals += len(findings.get("gitlab_matches", []))

    return {
        "status": "success",
        "summary": f"{signals} public identity enrichment signal(s) for {subject}.",
        "data": findings,
    }
