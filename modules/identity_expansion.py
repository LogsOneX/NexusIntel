import re
from urllib.parse import quote_plus

from core.targets import classify_target


metadata = {
    "name": "Identity Expansion",
    "description": "Offline username permutations, handle aliases, search pivots, and flow hints for deeper identity investigations.",
    "category": "identity",
    "target_types": ["username", "email", "url", "domain", "unknown"],
    "tags": ["identity", "permutation", "pivot", "offline"],
    "passive": True,
    "risk": "low",
}


SEPARATORS = ("", ".", "_", "-")


async def run(target: str) -> dict:
    profile = classify_target(target)
    seeds = _seed_values(target, profile)
    variants = _variants(seeds)
    pivots = _search_pivots(target, profile, variants[:8])
    identity_links = _identity_links(profile, variants[:12])
    recommended = _recommended_flows(profile.kind)

    signals = [
        {"type": "username_variant", "value": item["username"], "confidence": item["confidence"]}
        for item in variants[:20]
    ]
    signals.extend({"type": "pivot", "value": item["url"], "provider": item["provider"]} for item in pivots[:20])

    return {
        "status": "success",
        "summary": f"{len(variants)} username variant(s), {len(pivots)} passive pivot(s), {len(recommended)} flow hint(s).",
        "data": {
            "target": target,
            "target_type": profile.kind,
            "seeds": seeds,
            "username_variants": variants,
            "identity_links": identity_links,
            "public_search_pivots": pivots,
            "flow_hints": recommended,
            "signals": signals,
        },
    }


def _seed_values(target: str, profile) -> list[str]:
    raw = target.strip()
    candidates = list(profile.candidate_usernames or [])
    if profile.email:
        local, _, domain = profile.email.partition("@")
        candidates.extend([local, domain.split(".")[0]])
    if profile.domain:
        candidates.append(profile.domain.split(".")[0])
    if profile.username:
        candidates.append(profile.username)
    candidates.extend(_split_identity_text(raw))
    return _dedupe(_clean_seed(item) for item in candidates if item)


def _split_identity_text(value: str) -> list[str]:
    text = re.sub(r"https?://", " ", value.lower())
    text = re.sub(r"[^a-z0-9._@+-]+", " ", text)
    chunks = [part for part in re.split(r"[\s/@]+", text) if part]
    expanded = []
    for chunk in chunks:
        expanded.append(chunk)
        expanded.extend(part for part in re.split(r"[._+-]+", chunk) if len(part) > 1)
    return expanded


def _variants(seeds: list[str]) -> list[dict]:
    values: list[tuple[str, str, float]] = []
    for seed in seeds:
        parts = [part for part in re.split(r"[._+-]+", seed.lower()) if part]
        compact = "".join(parts) if parts else seed.lower()
        if 2 <= len(compact) <= 32:
            values.append((compact, "compact", 0.78))

        if len(parts) >= 2:
            first, last = parts[0], parts[-1]
            for sep in SEPARATORS:
                values.append((f"{first}{sep}{last}", "first_last", 0.72))
                values.append((f"{last}{sep}{first}", "last_first", 0.52))
            values.append((f"{first[0]}{last}", "initial_last", 0.66))
            values.append((f"{first}{last[0]}", "first_initial", 0.58))

        base = re.sub(r"\d+$", "", compact)
        if base and base != compact and len(base) >= 3:
            values.append((base, "numeric_suffix_removed", 0.54))
        if len(compact) >= 4:
            values.append((f"{compact}.dev", "developer_alias", 0.35))
            values.append((f"{compact}_", "underscore_alias", 0.32))

    cleaned = []
    seen = set()
    for username, reason, confidence in values:
        username = re.sub(r"[^a-z0-9._-]", "", username.lower()).strip("._-")
        if not (2 <= len(username) <= 32) or username in seen:
            continue
        seen.add(username)
        cleaned.append({"username": username, "reason": reason, "confidence": round(confidence, 2)})
    return sorted(cleaned, key=lambda item: (-item["confidence"], item["username"]))[:80]


def _search_pivots(target: str, profile, variants: list[dict]) -> list[dict]:
    queries = []
    exact_target = f'"{profile.email or profile.normalized or target}"'
    queries.append(("Google Exact Target", "google", f"https://www.google.com/search?q={quote_plus(exact_target)}"))
    queries.append(("Bing Exact Target", "bing", f"https://www.bing.com/search?q={quote_plus(exact_target)}"))
    queries.append(("GitHub Code", "github", f"https://github.com/search?q={quote_plus(exact_target)}&type=code"))
    if profile.domain:
        domain_query = quote_plus(f"site:{profile.domain} contact OR profile OR team")
        queries.append(("Domain People Surface", "google", f"https://www.google.com/search?q={domain_query}"))
    for item in variants[:6]:
        username = item["username"]
        quoted = quote_plus(f'"{username}"')
        queries.append((f"Cross Platform {username}", "google", f"https://www.google.com/search?q={quoted}+profile"))
        queries.append((f"GitHub Users {username}", "github", f"https://github.com/search?q={quote_plus(username)}&type=users"))
    return [
        {"name": name, "provider": provider, "url": url, "method": "manual_review"}
        for name, provider, url in _dedupe_tuples(queries)
    ][:40]


def _identity_links(profile, variants: list[dict]) -> list[dict]:
    links = []
    if profile.email:
        local, _, domain = profile.email.partition("@")
        links.append({"type": "email", "label": profile.email, "relationship": "seed"})
        links.append({"type": "domain", "label": domain, "relationship": "email_domain"})
        links.append({"type": "username", "label": local, "relationship": "email_localpart"})
    if profile.domain:
        links.append({"type": "domain", "label": profile.domain, "relationship": "seed"})
    for item in variants:
        links.append({"type": "username", "label": item["username"], "relationship": item["reason"], "confidence": item["confidence"]})
    return links[:50]


def _recommended_flows(kind: str) -> list[dict]:
    mapping = {
        "username": ["identity_deep", "identity_surface"],
        "email": ["identity_deep", "identity_surface", "domain_surface"],
        "domain": ["domain_surface"],
        "url": ["domain_surface"],
        "phone": ["phone_triage"],
    }
    return [{"flow_id": flow_id, "reason": f"recommended_for_{kind}"} for flow_id in mapping.get(kind, ["identity_surface"])]


def _clean_seed(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._+-]", "", value).strip("._+-").lower()


def _dedupe(values) -> list[str]:
    output = []
    seen = set()
    for value in values:
        if value and value not in seen:
            seen.add(value)
            output.append(value)
    return output


def _dedupe_tuples(values) -> list[tuple[str, str, str]]:
    output = []
    seen = set()
    for value in values:
        key = value[2]
        if key not in seen:
            seen.add(key)
            output.append(value)
    return output
