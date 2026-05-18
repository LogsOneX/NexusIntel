import re
from urllib.parse import urlparse


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9 .()_-]{6,}$")
DOMAIN_RE = re.compile(r"^(?:[a-zA-Z0-9-]+\.)+[a-zA-Z]{2,}$")


def classify_target(value: str) -> str:
    target = value.strip()
    if EMAIL_RE.match(target):
        return "email"
    if target.startswith(("http://", "https://")):
        return "url"
    if PHONE_RE.match(target):
        return "phone"
    if DOMAIN_RE.match(target):
        return "domain"
    if re.match(r"^[A-Za-z0-9_.-]{2,64}$", target):
        return "username"
    return "unknown"


def root_entity_type(target_type: str) -> str:
    return {
        "email": "email",
        "url": "website",
        "phone": "phone",
        "domain": "domain",
        "username": "username",
    }.get(target_type, "target")


def extract_domain(value: str) -> str | None:
    raw = value.strip()
    if "@" in raw:
        return raw.rsplit("@", 1)[-1].lower()
    if raw.startswith(("http://", "https://")):
        parsed = urlparse(raw)
        return parsed.netloc.split("@")[-1].split(":")[0].lower()
    if DOMAIN_RE.match(raw):
        return raw.lower()
    return None


def username_seed(value: str) -> str:
    raw = value.strip()
    if "@" in raw:
        raw = raw.split("@", 1)[0]
    if raw.startswith(("http://", "https://")):
        path = urlparse(raw).path.strip("/")
        if path:
            raw = path.split("/")[-1]
    return re.sub(r"[^A-Za-z0-9_.-]", "", raw)[:64]
