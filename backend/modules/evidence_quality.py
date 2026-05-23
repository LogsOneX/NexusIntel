from __future__ import annotations

from hashlib import sha256
from typing import Any

SYNTHETIC_MARKERS = (
    "dry_run",
    "dummy",
    "synthetic",
    "simulated",
    "placeholder",
    "fake",
)


def payload_sha256(payload: str | bytes) -> str:
    raw = payload.encode("utf-8", errors="replace") if isinstance(payload, str) else payload
    return sha256(raw).hexdigest()


def _truthy_marker(value: Any) -> bool:
    if value is False or value is None:
        return False
    if isinstance(value, (int, float)) and value == 0:
        return False
    if isinstance(value, str) and value.strip().lower() in {"", "0", "false", "none", "no"}:
        return False
    return True


def has_synthetic_marker(value: Any) -> bool:
    if isinstance(value, dict):
        for key, item in value.items():
            key_text = str(key).lower()
            if any(marker in key_text for marker in SYNTHETIC_MARKERS) and _truthy_marker(item):
                return True
            if has_synthetic_marker(item):
                return True
        return False
    if isinstance(value, (list, tuple, set)):
        return any(has_synthetic_marker(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        return any(marker in lowered for marker in SYNTHETIC_MARKERS)
    return False


def verified_public_result(result: dict[str, Any]) -> bool:
    return bool(result.get("verified")) and not has_synthetic_marker(result)


def evidence_grade(result: dict[str, Any]) -> str:
    if verified_public_result(result) and (result.get("source_url") or result.get("source")):
        return "A1"
    if verified_public_result(result):
        return "A2"
    return "UNVERIFIED"


def with_quality(result: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(result)
    enriched["synthetic"] = False
    enriched["evidence_grade"] = evidence_grade(enriched)
    return enriched
