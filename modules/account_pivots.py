from urllib.parse import quote_plus

import httpx

from core.targets import classify_target


metadata = {
    "name": "Account Pivot Enrichment",
    "description": "Email, domain, and username pivots across public account, workspace, developer, and well-known app-link signals.",
    "category": "identity",
    "target_types": ["email", "username", "domain"],
    "tags": ["account", "workspace", "github", "gitlab", "well-known", "public-api"],
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


def _provider_signals(mx_records: list[str], txt_records: list[str]) -> dict:
    mx_text = " ".join(mx_records).lower()
    txt_text = " ".join(txt_records).lower()
    providers = []
    checks = {
        "Google Workspace": ("google", "aspmx.l.google.com"),
        "Microsoft 365": ("protection.outlook.com", "outlook.com"),
        "Zoho Mail": ("zoho",),
        "Proton Mail": ("protonmail", "proton.ch"),
        "Fastmail": ("fastmail",),
        "Yandex": ("yandex",),
        "Mailgun": ("mailgun",),
        "SendGrid": ("sendgrid",),
    }
    for provider, markers in checks.items():
        if any(marker in mx_text or marker in txt_text for marker in markers):
            providers.append(provider)
    return {
        "providers": providers,
        "spf": "v=spf1" in txt_text,
        "google_site_verification": "google-site-verification" in txt_text,
        "dmarc_policy_hint": _txt_policy(txt_records, "v=dmarc1"),
    }


def _txt_policy(records: list[str], marker: str) -> str | None:
    for record in records:
        clean = record.strip('"').lower()
        if marker in clean:
            return clean[:240]
    return None


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


async def _npm_profile(client: httpx.AsyncClient, username: str) -> dict:
    try:
        response = await client.get(f"https://registry.npmjs.org/-/user/org.couchdb.user:{username}")
        if response.status_code != 200:
            return {"status": response.status_code}
        data = response.json()
        return {
            "username": data.get("name"),
            "email": data.get("email"),
            "created": data.get("date"),
        }
    except Exception as exc:
        return {"error": str(exc)}


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


async def _digital_asset_links(client: httpx.AsyncClient, domain: str) -> list[dict]:
    url = f"https://{domain}/.well-known/assetlinks.json"
    try:
        response = await client.get(url, follow_redirects=True)
        if response.status_code != 200:
            return []
        data = response.json()
    except Exception:
        return []
    if not isinstance(data, list):
        return []
    assets = []
    for item in data[:30]:
        if not isinstance(item, dict):
            continue
        target = item.get("target") if isinstance(item.get("target"), dict) else {}
        assets.append(
            {
                "namespace": target.get("namespace"),
                "package_name": target.get("package_name") or target.get("site"),
                "relations": item.get("relation", []),
                "fingerprints_count": len(target.get("sha256_cert_fingerprints", []) or []),
                "source_url": url,
            }
        )
    return [item for item in assets if item.get("package_name")]


async def _apple_app_site_association(client: httpx.AsyncClient, domain: str) -> dict:
    url = f"https://{domain}/.well-known/apple-app-site-association"
    try:
        response = await client.get(url, follow_redirects=True)
        if response.status_code != 200:
            return {"status": response.status_code, "apps": []}
        data = response.json()
    except Exception as exc:
        return {"error": str(exc), "apps": []}

    apps = []
    applinks = data.get("applinks") if isinstance(data, dict) else {}
    details = applinks.get("details", []) if isinstance(applinks, dict) else []
    for item in details[:30]:
        if not isinstance(item, dict):
            continue
        app_id = item.get("appID") or item.get("appIDs")
        if isinstance(app_id, list):
            apps.extend(str(value) for value in app_id)
        elif app_id:
            apps.append(str(app_id))
    return {"status": "found" if apps else "empty", "apps": sorted(set(apps))[:30], "source_url": url}


async def run(target: str) -> dict:
    profile = classify_target(target)
    subject = profile.normalized
    username = profile.candidate_usernames[0] if profile.candidate_usernames else None
    domain = profile.domain

    findings = {
        "target": subject,
        "target_type": profile.kind,
        "provider": None,
        "workspace_signals": [],
        "public_search_pivots": [],
        "digital_asset_links": [],
        "apple_app_links": {"apps": []},
    }

    headers = {"User-Agent": "Mozilla/5.0 NexusRecon/2.0"}
    async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
        if domain:
            mx_records = await _dns(client, domain, "MX")
            txt_records = await _dns(client, domain, "TXT")
            dmarc_records = await _dns(client, f"_dmarc.{domain}", "TXT")
            findings["mx_records"] = mx_records
            findings["txt_records"] = txt_records[:20]
            findings["dmarc_records"] = dmarc_records[:10]
            findings["mail_provider_signals"] = _provider_signals(mx_records, txt_records + dmarc_records)
            if findings["mail_provider_signals"]["providers"]:
                findings["provider"] = findings["mail_provider_signals"]["providers"][0]
                findings["workspace_signals"].extend(findings["mail_provider_signals"]["providers"])
            if findings["mail_provider_signals"]["google_site_verification"]:
                findings["workspace_signals"].append("google_site_verification_txt")
            dal_task = _digital_asset_links(client, domain)
            apple_task = _apple_app_site_association(client, domain)
            findings["digital_asset_links"], findings["apple_app_links"] = await dal_task, await apple_task

        if profile.email and profile.email.endswith(("@gmail.com", "@googlemail.com")):
            findings["provider"] = "Google consumer account domain"
            findings["workspace_signals"].append("gmail_domain")

        if username:
            findings["github"] = await _github_profile(client, username)
            findings["gitlab_matches"] = await _gitlab_matches(client, username)
            findings["npm"] = await _npm_profile(client, username)

    if profile.email:
        encoded = quote_plus(f'"{profile.email}"')
        findings["public_search_pivots"].extend(
            [
                f"https://www.google.com/search?q={encoded}",
                f"https://www.bing.com/search?q={encoded}",
                f"https://github.com/search?q={encoded}&type=code",
                f"https://gitlab.com/search?search={encoded}",
            ]
        )
    if username:
        encoded_user = quote_plus(username)
        findings["public_search_pivots"].extend(
            [
                f"https://www.google.com/search?q={encoded_user}",
                f"https://github.com/search?q={encoded_user}&type=users",
                f"https://gitlab.com/search?search={encoded_user}",
                f"https://www.npmjs.com/search?q={encoded_user}",
            ]
        )

    signals = len(findings.get("workspace_signals", []))
    if findings.get("github", {}).get("profile"):
        signals += 1
    signals += len(findings.get("gitlab_matches", []))
    if findings.get("npm", {}).get("username"):
        signals += 1
    signals += len(findings.get("digital_asset_links", []))
    signals += len(findings.get("apple_app_links", {}).get("apps", []))

    return {
        "status": "success",
        "summary": f"{signals} public identity enrichment signal(s) for {subject}.",
        "data": findings,
    }
