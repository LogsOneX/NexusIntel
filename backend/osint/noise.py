from __future__ import annotations

from typing import Any

NOISE_MARKERS = (
    "generic page", "generic pages", "generic login page", "generic signup page",
    "auth wall only", "authentication wall only", "soft 404", "soft-404",
    "parked domain", "false-positive profile", "false positive profile",
    "cloudflare challenge", "cdn/shared hosting", "registrar privacy",
    "generic messenger landing", "low value phone deeplink",
)

COMPLIANCE_MARKERS = (
    "guardrail", "legal_note", "legal note", "policy boundary", "compliance",
    "skipped_check", "skipped check", "blocked_transform", "prohibited probe",
)

CANDIDATE_MARKERS = (
    "candidate_url_only", "candidate profile", "profile candidate", "possible profile",
    "possible same actor", "username candidate", "email candidate", "phone deeplink candidate",
)

EVIDENCE_MARKERS = (
    "raw html", "raw_html", "raw json", "raw_json", "http response", "source_url",
    "dns record", "rdap record", "certificate", "file hash", "exif metadata",
)


def norm(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", "_").replace(" ", "_")


def has_marker(blob: str, markers: tuple[str, ...]) -> bool:
    normalized = blob.lower().replace("-", "_")
    return any(marker.replace(" ", "_").lower() in normalized for marker in markers)
