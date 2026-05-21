from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urlparse

import dns.reversename
import dns.resolver
import httpx


EMAIL_RE = re.compile(r"^(?=.{6,254}$)[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I)
USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,63}$")
E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")

DISPOSABLE_DOMAINS = {
    "10minutemail.com",
    "guerrillamail.com",
    "mailinator.com",
    "tempmail.com",
    "temp-mail.org",
    "trashmail.com",
    "yopmail.com",
    "sharklasers.com",
    "getnada.com",
    "dispostable.com",
}

COUNTRY_CALLING_CODES = {
    "1": {"region": "North America", "type": "nanp"},
    "44": {"region": "United Kingdom", "type": "national_plan"},
    "49": {"region": "Germany", "type": "national_plan"},
    "55": {"region": "Brazil", "type": "national_plan"},
    "60": {"region": "Malaysia", "type": "national_plan"},
    "61": {"region": "Australia", "type": "national_plan"},
    "62": {"region": "Indonesia", "type": "national_plan"},
    "63": {"region": "Philippines", "type": "national_plan"},
    "65": {"region": "Singapore", "type": "national_plan"},
    "81": {"region": "Japan", "type": "national_plan"},
    "82": {"region": "South Korea", "type": "national_plan"},
    "86": {"region": "China", "type": "national_plan"},
    "91": {"region": "India", "type": "national_plan"},
}

INDONESIA_MOBILE_PREFIXES = {
    "811", "812", "813", "821", "822", "823", "851", "852", "853", "855", "856", "857", "858", "859",
    "877", "878", "879", "881", "882", "883", "884", "885", "886", "887", "888", "889", "895", "896",
    "897", "898", "899",
}

PUBLIC_PLATFORM_TEMPLATES = [
    ("GitHub", "https://github.com/{username}", "tech"),
    ("GitLab", "https://gitlab.com/{username}", "tech"),
    ("Codeberg", "https://codeberg.org/{username}", "tech"),
    ("Dev.to", "https://dev.to/{username}", "tech"),
    ("Reddit", "https://reddit.com/user/{username}", "social"),
    ("X", "https://x.com/{username}", "social"),
    ("Instagram", "https://instagram.com/{username}", "social"),
    ("YouTube", "https://youtube.com/@{username}", "social"),
    ("Medium", "https://medium.com/@{username}", "blog"),
    ("LinkedIn", "https://linkedin.com/in/{username}", "professional"),
    ("Keybase", "https://keybase.io/{username}", "identity"),
    ("Linktree", "https://linktr.ee/{username}", "identity"),
]

GUARDRAILS = [
    "No credential stuffing.",
    "No private API/session use.",
    "No register or forgot-password probing.",
    "No rate-limit evasion.",
    "No phone/email account-existence probing on messaging or social apps.",
]


@dataclass
class ReconArtifact:
    type: str
    label: str
    value: str
    source: str
    confidence: str = "medium"
    relationship: str = "derived_signal"
    data: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "label": self.label,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "relationship": self.relationship,
            "data": self.data or {},
        }


def normalize_domain(value: str) -> str:
    raw = value.strip().lower()
    if "://" in raw:
        raw = urlparse(raw).netloc
    return raw.split("/")[0].split(":")[0].strip(".")


def normalize_username(value: str) -> str:
    raw = value.strip()
    if raw.startswith("@"):
        raw = raw[1:]
    if "/" in raw:
        raw = raw.rstrip("/").split("/")[-1]
        if raw.startswith("@"):
            raw = raw[1:]
    return re.sub(r"[^A-Za-z0-9._-]", "", raw)


def target_kind(value: str) -> str:
    candidate = value.strip()
    if EMAIL_RE.match(candidate):
        return "email"
    if E164_RE.match(candidate.replace(" ", "")):
        return "phone"
    try:
        ipaddress.ip_address(candidate)
        return "ip"
    except ValueError:
        pass
    if DOMAIN_RE.match(normalize_domain(candidate)):
        return "domain"
    if " " in candidate:
        return "name"
    return "username"


def resolve_dns(name: str, record_type: str, lifetime: float = 5.0) -> list[str]:
    try:
        answers = dns.resolver.resolve(name, record_type, lifetime=lifetime)
    except Exception:
        return []

    values: list[str] = []
    for answer in answers:
        if record_type == "MX":
            values.append(str(answer.exchange).rstrip("."))
        elif record_type == "TXT":
            chunks = getattr(answer, "strings", None)
            if chunks:
                values.append("".join(part.decode("utf-8", "ignore") for part in chunks))
            else:
                values.append(str(answer).strip('"'))
        else:
            values.append(str(answer).rstrip("."))
    return sorted(set(values))


async def fetch_json(url: str, timeout: float = 8.0) -> Any:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers={"User-Agent": "NexusIntel/1.0 public-osint"}) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()


async def crtsh_subdomains(domain: str) -> list[str]:
    url = f"https://crt.sh/?q=%25.{quote(domain)}&output=json"
    try:
        data = await fetch_json(url, timeout=12.0)
    except Exception:
        return []

    names: set[str] = set()
    if isinstance(data, list):
        for row in data[:500]:
            raw = str(row.get("name_value", "")) if isinstance(row, dict) else ""
            for item in raw.splitlines():
                clean = item.lower().strip("*. ")
                if clean.endswith(domain) and DOMAIN_RE.match(clean):
                    names.add(clean)
    return sorted(names)[:100]


async def rdap_domain(domain: str) -> dict[str, Any] | None:
    try:
        data = await fetch_json(f"https://rdap.org/domain/{quote(domain)}", timeout=8.0)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return {
        "handle": data.get("handle"),
        "ldhName": data.get("ldhName"),
        "status": data.get("status"),
        "events": data.get("events", [])[:8],
        "nameservers": data.get("nameservers", [])[:12],
    }


async def rdap_ip(ip: str) -> dict[str, Any] | None:
    try:
        data = await fetch_json(f"https://rdap.org/ip/{quote(ip)}", timeout=8.0)
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    return {
        "handle": data.get("handle"),
        "name": data.get("name"),
        "type": data.get("type"),
        "country": data.get("country"),
        "startAddress": data.get("startAddress"),
        "endAddress": data.get("endAddress"),
        "parentHandle": data.get("parentHandle"),
        "status": data.get("status"),
    }


async def ip_api_geo(ip: str) -> dict[str, Any] | None:
    try:
        data = await fetch_json(
            f"http://ip-api.com/json/{quote(ip)}?fields=status,country,regionName,city,isp,org,as,query,proxy,hosting,mobile",
            timeout=8.0,
        )
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("status") != "success":
        return None
    return data


def reverse_dns(ip: str) -> list[str]:
    try:
        reverse = dns.reversename.from_address(ip)
        return resolve_dns(str(reverse), "PTR", lifetime=5.0)
    except Exception:
        try:
            return [socket.gethostbyaddr(ip)[0]]
        except Exception:
            return []


async def analyze_email_target(value: str, mode: str = "standard") -> dict[str, Any]:
    target = value.strip().lower()
    valid = bool(EMAIL_RE.match(target))
    local, domain = target.rsplit("@", 1) if "@" in target else (target, normalize_domain(target))
    artifacts: list[ReconArtifact] = []

    artifacts.append(
        ReconArtifact(
            "validation",
            "Email format",
            f"email:{target}:format",
            "email_recon",
            "high" if valid else "low",
            "has_validation",
            {"valid": valid, "regex": EMAIL_RE.pattern},
        )
    )
    if local:
        artifacts.append(ReconArtifact("username", local, local, "email_recon", "medium", "has_local_part", {"derived_from": target}))
    if domain:
        artifacts.append(ReconArtifact("domain", domain, domain, "email_recon", "high", "uses_domain", {"role": "mail_domain"}))

    mx = resolve_dns(domain, "MX") if domain else []
    txt = resolve_dns(domain, "TXT") if domain else []
    dmarc = resolve_dns(f"_dmarc.{domain}", "TXT") if domain else []
    bimi = resolve_dns(f"default._bimi.{domain}", "TXT") if domain else []
    disposable = domain in DISPOSABLE_DOMAINS

    for record_type, values in {"MX": mx, "TXT": txt, "DMARC": dmarc, "BIMI": bimi}.items():
        for item in values[:40]:
            artifacts.append(
                ReconArtifact(
                    "dns_record",
                    f"{record_type} {item[:72]}",
                    f"{record_type}:{domain}:{item}",
                    "dns",
                    "high",
                    "has_dns_record",
                    {"record_type": record_type, "record": item},
                )
            )

    artifacts.append(
        ReconArtifact(
            "signal",
            "Disposable email hint",
            f"disposable:{domain}:{disposable}",
            "email_recon",
            "high" if disposable else "low",
            "has_signal",
            {"disposable": disposable, "method": "offline_disposable_domain_list"},
        )
    )
    artifacts.append(
        ReconArtifact(
            "signal",
            "Mail exchanger posture",
            f"mail_accepts:{domain}:{bool(mx)}",
            "dns",
            "high" if mx else "low",
            "has_signal",
            {"has_mx": bool(mx), "mx_count": len(mx)},
        )
    )
    artifacts.append(
        ReconArtifact(
            "guardrail",
            "Unsafe registration probing skipped",
            f"guardrail:{target}:registration-probing",
            "policy",
            "confirmed",
            "has_guardrail",
            {
                "skipped_checks": ["platform_registration", "forgot_password", "private_api"],
                "reason": "public-source-only safety boundary",
            },
        )
    )
    artifacts.append(
        ReconArtifact(
            "guardrail",
            "Breach corpus lookup requires local dataset",
            f"guardrail:{target}:breach-corpus",
            "policy",
            "confirmed",
            "has_guardrail",
            {
                "skipped_checks": ["paid_breach_api", "credential_corpus_download"],
                "reason": "no bundled breach corpus and no paid/private API dependency",
            },
        )
    )

    return {
        "target": target,
        "kind": "email",
        "valid": valid,
        "local_part": local,
        "domain": domain,
        "has_mx": bool(mx),
        "disposable": disposable,
        "dns": {"MX": mx, "TXT": txt, "DMARC": dmarc, "BIMI": bimi},
        "guardrails": GUARDRAILS,
        "artifacts": [artifact.as_dict() for artifact in artifacts],
    }


async def analyze_network_target(value: str, mode: str = "standard") -> dict[str, Any]:
    target = value.strip()
    artifacts: list[ReconArtifact] = []
    try:
        ip = str(ipaddress.ip_address(target))
        ptr = reverse_dns(ip)
        rdap = await rdap_ip(ip) if mode in {"standard", "aggressive"} else None
        geo = await ip_api_geo(ip) if mode in {"standard", "aggressive"} else None
        for host in ptr:
            artifacts.append(ReconArtifact("domain", host, host, "reverse_dns", "medium", "reverse_resolves_to", {"ip": ip}))
        if rdap:
            artifacts.append(ReconArtifact("network", rdap.get("name") or rdap.get("handle") or ip, f"rdap:{ip}", "rdap", "medium", "has_rdap", rdap))
        if geo:
            artifacts.append(ReconArtifact("geoip", geo.get("as") or ip, f"geoip:{ip}", "ip-api", "medium", "has_geoip", geo))
        return {
            "target": ip,
            "kind": "ip",
            "ptr": ptr,
            "rdap": rdap,
            "geoip": geo,
            "artifacts": [artifact.as_dict() for artifact in artifacts],
            "guardrails": GUARDRAILS,
        }
    except ValueError:
        pass

    domain = normalize_domain(target)
    record_sets = {record: resolve_dns(domain, record) for record in ["A", "AAAA", "CNAME", "MX", "NS", "TXT", "CAA"]}
    rdap = await rdap_domain(domain) if mode in {"standard", "aggressive"} else None
    subdomains = await crtsh_subdomains(domain) if mode in {"standard", "aggressive"} else []

    artifacts.append(ReconArtifact("domain", domain, domain, "network_recon", "confirmed", "is_target", {"valid": bool(DOMAIN_RE.match(domain))}))
    for record_type, values in record_sets.items():
        for item in values[:60]:
            node_type = "ip" if record_type in {"A", "AAAA"} else "dns_record"
            rel = "resolves_to" if node_type == "ip" else "has_dns_record"
            artifacts.append(
                ReconArtifact(
                    node_type,
                    item if node_type == "ip" else f"{record_type} {item[:72]}",
                    item if node_type == "ip" else f"{record_type}:{domain}:{item}",
                    "dns",
                    "high",
                    rel,
                    {"record_type": record_type, "record": item},
                )
            )
    for subdomain in subdomains[:80]:
        artifacts.append(ReconArtifact("domain", subdomain, subdomain, "crtsh", "medium", "has_subdomain", {"source": "crt.sh"}))
    if rdap:
        artifacts.append(ReconArtifact("registration", rdap.get("ldhName") or domain, f"rdap:{domain}", "rdap", "medium", "has_rdap", rdap))

    return {
        "target": domain,
        "kind": "domain",
        "valid": bool(DOMAIN_RE.match(domain)),
        "dns": record_sets,
        "rdap": rdap,
        "subdomains": subdomains,
        "artifacts": [artifact.as_dict() for artifact in artifacts],
        "guardrails": GUARDRAILS,
    }


def analyze_phone_target(value: str, mode: str = "standard") -> dict[str, Any]:
    compact = re.sub(r"[\s().-]", "", value.strip())
    valid = bool(E164_RE.match(compact))
    digits = compact[1:] if compact.startswith("+") else compact
    calling_code = ""
    plan = None
    for size in [3, 2, 1]:
        code = digits[:size]
        if code in COUNTRY_CALLING_CODES:
            calling_code = code
            plan = COUNTRY_CALLING_CODES[code]
            break
    national = digits[len(calling_code):] if calling_code else digits
    line_type = "unknown"
    if calling_code == "62" and national[:3] in INDONESIA_MOBILE_PREFIXES:
        line_type = "mobile"
    elif calling_code:
        line_type = "numbering_plan_match"

    artifacts = [
        ReconArtifact(
            "phone",
            compact,
            compact,
            "phone_recon",
            "high" if valid else "low",
            "is_target",
            {"valid_e164": valid, "calling_code": calling_code, "national_number": national},
        ).as_dict(),
        ReconArtifact(
            "signal",
            "Line type hint",
            f"line_type:{compact}:{line_type}",
            "numbering_plan",
            "medium",
            "has_signal",
            {"line_type": line_type, "method": "offline_public_numbering_plan"},
        ).as_dict(),
        ReconArtifact(
            "guardrail",
            "Messaging app registration probing skipped",
            f"guardrail:{compact}:messaging-registration",
            "policy",
            "confirmed",
            "has_guardrail",
            {"skipped_checks": ["whatsapp", "telegram", "instagram"], "reason": "registration/account existence probing is not performed"},
        ).as_dict(),
    ]
    return {
        "target": compact,
        "kind": "phone",
        "valid_e164": valid,
        "calling_code": calling_code,
        "national_number": national,
        "line_type": line_type,
        "plan": plan,
        "artifacts": artifacts,
        "guardrails": GUARDRAILS,
    }


async def analyze_identity_target(value: str, mode: str = "standard") -> dict[str, Any]:
    raw = value.strip()
    username = normalize_username(raw)
    is_username = bool(USERNAME_RE.match(username))
    parts = [part for part in re.split(r"\s+", raw) if part]
    artifacts: list[ReconArtifact] = []
    if is_username:
        artifacts.append(ReconArtifact("username", username, username, "identity_recon", "confirmed", "is_target", {"valid_username_shape": True, "raw_input": raw}))
        for name, template, category in PUBLIC_PLATFORM_TEMPLATES:
            artifacts.append(
                ReconArtifact(
                    "profile_candidate",
                    f"{username} @ {name}",
                    template.format(username=username),
                    "identity_recon",
                    "low",
                    "candidate_profile",
                    {"platform": name, "category": category, "verification": "candidate_url_only"},
                )
            )
    else:
        artifacts.append(ReconArtifact("name", raw, raw, "identity_recon", "medium", "is_target", {"parts": parts, "part_count": len(parts)}))
        if parts:
            artifacts.append(ReconArtifact("name_part", parts[0], parts[0], "identity_recon", "medium", "has_name_part", {"position": "first"}))
        if len(parts) > 1:
            artifacts.append(ReconArtifact("name_part", parts[-1], parts[-1], "identity_recon", "medium", "has_name_part", {"position": "last"}))
    artifacts.append(
        ReconArtifact(
            "guardrail",
            "Sensitive cultural origin inference skipped",
            f"guardrail:{raw}:cultural-origin",
            "policy",
            "confirmed",
            "has_guardrail",
            {"reason": "name-origin inference can be sensitive and unreliable"},
        )
    )
    return {
        "target": username if is_username else raw,
        "raw_input": raw,
        "kind": "username" if is_username else "name",
        "valid_username_shape": is_username,
        "name_parts": parts,
        "artifacts": [artifact.as_dict() for artifact in artifacts],
        "guardrails": GUARDRAILS,
    }
