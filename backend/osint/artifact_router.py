from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from backend.osint.noise import CANDIDATE_MARKERS, COMPLIANCE_MARKERS, EVIDENCE_MARKERS, NOISE_MARKERS, has_marker, norm
from backend.osint.taxonomy import (
    CANDIDATE_TYPES,
    COMPLIANCE_TYPES,
    ENTITY_TYPES,
    EVIDENCE_TYPES,
    NOISE_TYPES,
    SIGNAL_TYPES,
    ArtifactClass,
    route_for_class,
)


def _data(artifact: dict[str, Any]) -> dict[str, Any]:
    return artifact.get("data") if isinstance(artifact.get("data"), dict) else {}


def _text_blob(artifact: dict[str, Any]) -> str:
    data = _data(artifact)
    tags = artifact.get("tags") or data.get("tags") or []
    payload = {
        "type": artifact.get("type"),
        "label": artifact.get("label"),
        "value": artifact.get("value"),
        "source": artifact.get("source"),
        "relationship": artifact.get("relationship"),
        "confidence": artifact.get("confidence"),
        "tags": tags,
        "data": data,
    }
    return json.dumps(payload, default=str).lower().replace("-", "_")


def classify_artifact(artifact: dict[str, Any]) -> ArtifactClass:
    artifact_type = norm(artifact.get("type"))
    relationship = norm(artifact.get("relationship"))
    source = norm(artifact.get("source"))
    label = norm(artifact.get("label"))
    value = norm(artifact.get("value"))
    data = _data(artifact)
    verification = norm(data.get("verification"))
    page_class = norm(data.get("page_class") or data.get("page_type") or data.get("noise_type"))
    graph_visibility = norm(data.get("graph_visibility"))
    artifact_class = norm(data.get("artifact_class") or data.get("classification"))
    blob = _text_blob(artifact)
    control_blob = " ".join([artifact_type, relationship, source, label, value, artifact_class, graph_visibility])

    if artifact_class in {"compliance", "policy"} or graph_visibility == "compliance_log":
        return "COMPLIANCE"
    if artifact_type in COMPLIANCE_TYPES or relationship in {"has_guardrail", "has_policy", "has_legal_note", "blocked_transform"}:
        return "COMPLIANCE"
    if has_marker(control_blob, COMPLIANCE_MARKERS) or source in {"guardrail", "policy", "compliance"}:
        return "COMPLIANCE"

    if artifact_class == "noise" or graph_visibility == "noise_bin":
        return "NOISE"
    if artifact_type in NOISE_TYPES or page_class in NOISE_TYPES:
        return "NOISE"
    if has_marker(blob, NOISE_MARKERS):
        return "NOISE"

    if artifact_class == "candidate" or graph_visibility == "candidate_bin":
        return "CANDIDATE"
    if artifact_type in CANDIDATE_TYPES or verification == "candidate_url_only" or page_class == "candidate_url_only":
        return "CANDIDATE"
    if has_marker(blob, CANDIDATE_MARKERS):
        return "CANDIDATE"

    if artifact_class == "evidence" or graph_visibility == "evidence_only":
        return "EVIDENCE"
    if artifact_type in EVIDENCE_TYPES or has_marker(control_blob, EVIDENCE_MARKERS):
        return "EVIDENCE"

    if artifact_class == "signal" or graph_visibility == "signal_badge":
        return "SIGNAL"
    if artifact_type in SIGNAL_TYPES:
        return "SIGNAL"

    if artifact_type in ENTITY_TYPES:
        return "ENTITY"
    return "ENTITY"


def route_artifact(artifact: dict[str, Any]):
    return route_for_class(classify_artifact(artifact))


def should_create_entity(artifact: dict[str, Any]) -> bool:
    return route_artifact(artifact).create_entity


def bucket_for_classification(classification: ArtifactClass) -> str | None:
    return route_for_class(classification).meta_bucket


def artifact_record_key(record: dict[str, Any]) -> str:
    stable = "|".join(str(record.get(part, "")).lower() for part in ("classification", "type", "value", "source", "relationship", "parent_id"))
    return hashlib.sha256(stable.encode("utf-8", errors="ignore")).hexdigest()[:24]


def artifact_record(
    artifact: dict[str, Any],
    classification: ArtifactClass,
    *,
    default_source: str = "system",
    parent_id: str | None = None,
) -> dict[str, Any]:
    data = _data(artifact)
    source = str(artifact.get("source") or default_source)
    label = str(artifact.get("label") or artifact.get("value") or artifact.get("type") or classification.lower())
    value = str(artifact.get("value") or label)
    route = route_for_class(classification)
    record = {
        "classification": classification,
        "artifact_class": classification,
        "graph_visibility": route.graph_visibility,
        "promotion_status": artifact.get("promotion_status") or data.get("promotion_status") or ("pending" if classification == "CANDIDATE" else "stored"),
        "type": str(artifact.get("type") or "signal"),
        "label": label,
        "value": value,
        "source": source,
        "source_url": artifact.get("source_url") or data.get("source_url"),
        "fetched_at": artifact.get("fetched_at") or data.get("fetched_at") or datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "confidence": artifact.get("confidence"),
        "confidence_score": artifact.get("confidence_score") or data.get("confidence_score"),
        "confidence_reason": artifact.get("confidence_reason") or data.get("confidence_reason"),
        "evidence_grade": artifact.get("evidence_grade") or data.get("evidence_grade"),
        "noise_reason": artifact.get("noise_reason") or data.get("noise_reason"),
        "relationship": artifact.get("relationship"),
        "raw_evidence_ref": artifact.get("raw_evidence_ref") or data.get("raw_evidence_ref"),
        "legal_basis": artifact.get("legal_basis") or data.get("legal_basis"),
        "public_source_note": artifact.get("public_source_note") or data.get("public_source_note"),
        "parent_id": parent_id,
        "data": data,
    }
    compact = {key: value for key, value in record.items() if value not in (None, "")}
    compact.setdefault("id", artifact_record_key(compact))
    return compact


def append_artifact_to_meta(meta: dict[str, Any] | None, bucket: str, record: dict[str, Any], *, limit: int = 500) -> dict[str, Any]:
    next_meta = dict(meta or {})
    items = [item for item in (next_meta.get(bucket) or []) if isinstance(item, dict)]
    key = record.get("id") or artifact_record_key(record)
    record = {**record, "id": key}
    updated = False
    next_items: list[dict[str, Any]] = []
    for item in items:
        item_key = item.get("id") or artifact_record_key(item)
        if item_key == key:
            next_items.append({**item, **record})
            updated = True
        else:
            next_items.append({**item, "id": item_key})
    if not updated:
        next_items.append(record)
    next_meta[bucket] = next_items[-limit:]
    counts = dict(next_meta.get("artifact_counts") or {})
    counts["candidate_count"] = len(next_meta.get("leads") or [])
    counts["noise_count"] = len(next_meta.get("noise") or [])
    counts["compliance_count"] = len(next_meta.get("compliance") or [])
    next_meta["artifact_counts"] = counts
    return next_meta


def dedupe_records(*collections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for collection in collections:
        for item in collection:
            if not isinstance(item, dict):
                continue
            key = str(item.get("id") or artifact_record_key(item))
            if key in seen:
                continue
            seen.add(key)
            merged.append({**item, "id": key})
    return merged
