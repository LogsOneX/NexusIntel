import re
from dataclasses import dataclass
from ipaddress import ip_address
from typing import List, Optional
from urllib.parse import urlparse


EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
DOMAIN_RE = re.compile(
    r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$"
)
USERNAME_RE = re.compile(r"[^A-Za-z0-9_.@-]")


@dataclass(frozen=True)
class TargetProfile:
    original: str
    normalized: str
    kind: str
    username: Optional[str] = None
    email: Optional[str] = None
    domain: Optional[str] = None
    url: Optional[str] = None
    phone: Optional[str] = None
    ip: Optional[str] = None
    notes: Optional[str] = None

    @property
    def candidate_usernames(self) -> List[str]:
        candidates: List[str] = []
        if self.username:
            candidates.append(self.username)
        if self.email:
            candidates.append(self.email.split("@", 1)[0])
        if self.url:
            parsed = urlparse(self.url)
            path_tail = parsed.path.strip("/").split("/")[-1]
            if path_tail:
                candidates.append(path_tail)

        deduped: List[str] = []
        for item in candidates:
            clean = sanitize_username(item)
            if clean and clean not in deduped:
                deduped.append(clean)
        return deduped


def sanitize_username(value: str) -> str:
    return USERNAME_RE.sub("", value.strip())


def strip_scheme(value: str) -> str:
    return re.sub(r"^https?://", "", value.strip(), flags=re.IGNORECASE)


def normalize_domain(value: str) -> str:
    raw = strip_scheme(value).split("/")[0].split("?")[0].strip().lower()
    if raw.startswith("www."):
        raw = raw[4:]
    return raw


def normalize_url(value: str) -> str:
    raw = value.strip()
    if not raw.startswith(("http://", "https://")):
        raw = f"https://{raw}"
    return raw


def classify_target(target: str) -> TargetProfile:
    raw = target.strip()
    if not raw:
        return TargetProfile(original=target, normalized="", kind="unknown", notes="Empty target.")

    try:
        parsed_ip = ip_address(raw)
        return TargetProfile(original=target, normalized=str(parsed_ip), kind="ip", ip=str(parsed_ip))
    except ValueError:
        pass

    if EMAIL_RE.fullmatch(raw):
        domain = raw.split("@", 1)[1].lower()
        return TargetProfile(
            original=target,
            normalized=raw.lower(),
            kind="email",
            email=raw.lower(),
            domain=domain,
            username=sanitize_username(raw.split("@", 1)[0]),
        )

    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    if parsed.netloc and "." in parsed.netloc:
        domain = normalize_domain(raw)
        if DOMAIN_RE.fullmatch(domain):
            return TargetProfile(
                original=target,
                normalized=domain,
                kind="url" if "/" in strip_scheme(raw) else "domain",
                domain=domain,
                url=normalize_url(raw),
                username=sanitize_username(parsed.path.strip("/").split("/")[-1]) if parsed.path.strip("/") else None,
            )

    digits = re.sub(r"\D", "", raw)
    if 7 <= len(digits) <= 15 and len(digits) >= max(7, len(raw) // 2):
        normalized = f"+{digits}"
        return TargetProfile(original=target, normalized=normalized, kind="phone", phone=normalized)

    clean_username = sanitize_username(raw.split("/")[-1])
    if clean_username:
        return TargetProfile(
            original=target,
            normalized=clean_username,
            kind="username",
            username=clean_username,
        )

    return TargetProfile(original=target, normalized=raw, kind="unknown", notes="Unable to classify target.")
