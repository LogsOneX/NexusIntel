from __future__ import annotations

import ipaddress
from urllib.parse import urlparse, urlunparse

def normalize_value(kind: str, value: str) -> str:
    raw = (value or "").strip()
    if kind in {"email", "domain", "subdomain", "hash", "sha256", "md5", "crypto_wallet", "wallet_address"}:
        return raw.lower()
    if kind == "url":
        parsed = urlparse(raw if "://" in raw else "https://" + raw)
        netloc = parsed.netloc.lower()
        path = parsed.path or "/"
        return urlunparse((parsed.scheme.lower() or "https", netloc, path, "", parsed.query, ""))
    if kind in {"ip", "ipv4", "ipv6"}:
        try:
            return str(ipaddress.ip_address(raw))
        except ValueError:
            return raw
    return " ".join(raw.split())
