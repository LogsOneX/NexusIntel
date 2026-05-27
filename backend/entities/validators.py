from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$")
SHA256_RE = re.compile(r"^[a-fA-F0-9]{64}$")
MD5_RE = re.compile(r"^[a-fA-F0-9]{32}$")

def validate_value(kind: str, value: str) -> tuple[bool, str | None]:
    value = (value or "").strip()
    if not value:
        return False, "empty_value"
    if kind == "email":
        return bool(EMAIL_RE.match(value)), None if EMAIL_RE.match(value) else "invalid_email"
    if kind == "domain":
        return bool(DOMAIN_RE.match(value)), None if DOMAIN_RE.match(value) else "invalid_domain"
    if kind == "url":
        parsed = urlparse(value)
        ok = parsed.scheme in {"http", "https"} and bool(parsed.netloc)
        return ok, None if ok else "invalid_public_url"
    if kind == "ip":
        try:
            ipaddress.ip_address(value)
            return True, None
        except ValueError:
            return False, "invalid_ip"
    if kind == "sha256":
        return bool(SHA256_RE.match(value)), None if SHA256_RE.match(value) else "invalid_sha256"
    if kind == "md5":
        return bool(MD5_RE.match(value)), None if MD5_RE.match(value) else "invalid_md5"
    return True, None
