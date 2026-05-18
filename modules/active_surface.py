import asyncio
from typing import Any
from urllib.parse import urlparse

import httpx

from core.targets import classify_target, normalize_domain


metadata = {
    "name": "Active Surface Sweep",
    "description": "Active public-source DNS, robots/sitemap, common-path, and host reachability sweep for owned or authorized targets.",
    "category": "infrastructure",
    "target_types": ["domain", "url", "email"],
    "tags": ["active", "surface", "dns", "crawl", "http"],
    "passive": False,
    "risk": "medium",
}


COMMON_HOSTS = [
    "www", "api", "app", "admin", "portal", "login", "mail", "smtp", "imap", "mx", "cdn",
    "dev", "staging", "stage", "test", "beta", "assets", "static", "blog", "docs", "status",
    "support", "help", "vpn", "sso", "id", "auth", "grafana", "kibana", "git", "jira",
    "confluence", "jenkins", "ci", "registry", "docker", "monitor", "m", "shop", "store",
]

COMMON_PATHS = [
    "/", "/robots.txt", "/sitemap.xml", "/.well-known/security.txt", "/.well-known/assetlinks.json",
    "/.well-known/apple-app-site-association", "/security.txt", "/humans.txt", "/status",
    "/health", "/api/health", "/login", "/admin", "/docs", "/swagger.json", "/openapi.json",
]


async def run(target: str, mode: str = "standard") -> dict:
    if mode not in {"active", "aggressive"}:
        return {
            "status": "skipped",
            "summary": "Active sweep disabled in standard mode.",
            "data": {"target": target, "mode": mode, "enable_with": "--mode active or --aggressive"},
        }

    profile = classify_target(target)
    domain = profile.domain or normalize_domain(target) or urlparse(profile.url or "").netloc.lower()
    if not domain:
        return {"status": "skipped", "summary": "No domain candidate for active sweep.", "data": {"target": target, "mode": mode}}

    hostname_limit = 18 if mode == "active" else len(COMMON_HOSTS)
    path_limit = 8 if mode == "active" else len(COMMON_PATHS)
    timeout = 6.0 if mode == "active" else 9.0
    headers = {"User-Agent": f"Mozilla/5.0 NexusRecon/2.0 active-surface/{mode}"}

    limits = httpx.Limits(max_connections=18 if mode == "active" else 35, max_keepalive_connections=10)
    async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True, limits=limits) as client:
        dns_tasks = [_resolve_host(client, f"{host}.{domain}") for host in COMMON_HOSTS[:hostname_limit]]
        path_tasks = [_probe_path(client, domain, path) for path in COMMON_PATHS[:path_limit]]
        dns_results, path_results = await asyncio.gather(asyncio.gather(*dns_tasks), asyncio.gather(*path_tasks))

    live_hosts = [item for item in dns_results if item.get("addresses")]
    interesting_paths = [item for item in path_results if item.get("status_code") and item["status_code"] < 500]
    technologies = _technology_hints(interesting_paths)
    risk = _risk(live_hosts, interesting_paths)

    data: dict[str, Any] = {
        "mode": mode,
        "domain": domain,
        "hostname_candidates": dns_results,
        "live_hosts": live_hosts,
        "path_probes": path_results,
        "interesting_paths": interesting_paths,
        "technology_hints": technologies,
        "risk": risk,
        "signals": [
            {"type": "live_host", "value": item["hostname"], "addresses": item["addresses"]}
            for item in live_hosts
        ] + [
            {"type": "interesting_path", "value": item["url"], "status_code": item["status_code"]}
            for item in interesting_paths
        ],
    }
    signal_count = len(live_hosts) + len(interesting_paths) + len(technologies)
    return {
        "status": "success",
        "summary": f"{signal_count} active surface signal(s), risk={risk['risk_level']} for {domain}.",
        "data": data,
    }


async def _resolve_host(client: httpx.AsyncClient, hostname: str) -> dict:
    try:
        response = await client.get("https://dns.google/resolve", params={"name": hostname, "type": "A"})
        if response.status_code != 200:
            return {"hostname": hostname, "addresses": [], "status": response.status_code}
        addresses = [answer.get("data") for answer in response.json().get("Answer", []) if answer.get("data")]
        return {"hostname": hostname, "addresses": addresses[:8], "status": "resolved" if addresses else "empty"}
    except Exception as exc:
        return {"hostname": hostname, "addresses": [], "error": str(exc)}


async def _probe_path(client: httpx.AsyncClient, domain: str, path: str) -> dict:
    url = f"https://{domain}{path}"
    try:
        response = await client.get(url)
        return {
            "url": str(response.url),
            "path": path,
            "status_code": response.status_code,
            "content_type": response.headers.get("content-type", ""),
            "server": response.headers.get("server", ""),
            "title": _title(response.text[:80000]),
            "body_size": len(response.content),
        }
    except Exception as exc:
        return {"url": url, "path": path, "error": str(exc)}


def _title(body: str) -> str | None:
    lower = body.lower()
    start = lower.find("<title")
    if start == -1:
        return None
    start = lower.find(">", start)
    end = lower.find("</title>", start)
    if start == -1 or end == -1:
        return None
    return " ".join(body[start + 1:end].split())[:120]


def _technology_hints(paths: list[dict]) -> list[dict]:
    hints = []
    for item in paths:
        text = " ".join([item.get("server", ""), item.get("content_type", ""), item.get("title") or ""]).lower()
        for name, marker in {
            "nginx": "nginx",
            "apache": "apache",
            "cloudflare": "cloudflare",
            "openapi": "openapi",
            "swagger": "swagger",
            "json-api": "application/json",
        }.items():
            if marker in text:
                hints.append({"name": name, "source": item.get("url")})
    unique = {}
    for hint in hints:
        unique.setdefault((hint["name"], hint["source"]), hint)
    return list(unique.values())[:40]


def _risk(live_hosts: list[dict], paths: list[dict]) -> dict:
    reasons = []
    score = 0
    host_names = " ".join(item.get("hostname", "") for item in live_hosts).lower()
    if any(marker in host_names for marker in ("dev.", "staging.", "stage.", "test.", "jenkins.", "grafana.", "kibana.")):
        score += 25
        reasons.append("sensitive_environment_hostname")
    for item in paths:
        path = item.get("path", "")
        if path in {"/admin", "/login", "/swagger.json", "/openapi.json"} and item.get("status_code") in {200, 301, 302, 401, 403}:
            score += 10
            reasons.append(f"interesting_path:{path}")
    level = "low"
    if score >= 25:
        level = "medium"
    if score >= 55:
        level = "high"
    return {"risk_score": min(score, 100), "risk_level": level, "reasons": sorted(set(reasons))}
