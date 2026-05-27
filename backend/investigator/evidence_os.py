from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from backend.modules.provenance_store import ProvenanceStore


def _iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        try:
            text = value.isoformat(timespec="seconds")
        except TypeError:
            text = value.isoformat()
        if text.endswith("Z"):
            return text
        if text.endswith("+00:00"):
            text = text[:-6]
        return f"{text}Z"
    return str(value)


def _iso_or_unknown(value: Any) -> str:
    return _iso_or_none(value) or "not_available"


def _read_text(uri: str, limit: int = 20_000) -> tuple[str, bool]:
    path = Path(uri)
    if not path.exists() or not path.is_file():
        return "", False
    raw = path.read_bytes()
    return raw[:limit].decode("utf-8", errors="replace"), len(raw) > limit


def evidence_excerpt(record: Any, limit: int = 2_000) -> dict[str, Any]:
    text, truncated = _read_text(str(record.uri), limit)
    return {
        "evidence_id": record.id,
        "source": record.source,
        "source_url": (record.meta or {}).get("source_url") or record.uri,
        "fetched_at": (record.meta or {}).get("fetched_at") or _iso_or_unknown(record.created_at),
        "sha256": record.sha256,
        "content_type": record.content_type,
        "status_code": (record.meta or {}).get("status_code") or (record.meta or {}).get("http_status"),
        "excerpt": text,
        "truncated": truncated,
    }


def verify_evidence(record: Any) -> dict[str, Any]:
    verification = ProvenanceStore().verify(str(record.uri), str(record.sha256))
    meta = record.meta or {}
    return {
        "evidence_id": record.id,
        "ok": bool(verification.get("ok")),
        "expected_sha256": record.sha256,
        "actual_sha256": verification.get("sha256"),
        "source_url": meta.get("source_url") or record.uri,
        "fetched_at": meta.get("fetched_at") or _iso_or_unknown(record.created_at),
        "status_code": meta.get("status_code") or meta.get("http_status"),
        "reason": verification.get("reason") or ("sha256 match" if verification.get("ok") else "sha256 mismatch"),
    }


def diff_evidence(left: Any, right: Any, limit: int = 20_000) -> dict[str, Any]:
    left_text, left_truncated = _read_text(str(left.uri), limit)
    right_text, right_truncated = _read_text(str(right.uri), limit)
    diff = list(
        difflib.unified_diff(
            left_text.splitlines(),
            right_text.splitlines(),
            fromfile=f"{left.id}:{left.sha256[:12]}",
            tofile=f"{right.id}:{right.sha256[:12]}",
            lineterm="",
        )
    )
    return {
        "left_id": left.id,
        "right_id": right.id,
        "left_sha256": left.sha256,
        "right_sha256": right.sha256,
        "changed": left.sha256 != right.sha256,
        "diff": diff[:800],
        "truncated": left_truncated or right_truncated or len(diff) > 800,
    }


def build_evidence_map(graph: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_by_id = {str(item.get("id")): item for item in evidence if item.get("id")}
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    node_map: dict[str, list[dict[str, Any]]] = {}
    edge_map: dict[str, list[dict[str, Any]]] = {}
    unsupported: list[dict[str, Any]] = []

    def compact(record: dict[str, Any]) -> dict[str, Any]:
        meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
        return {
            "evidence_id": record.get("id"),
            "source": record.get("source"),
            "source_url": meta.get("source_url") or record.get("uri"),
            "fetched_at": meta.get("fetched_at") or record.get("created_at"),
            "sha256": record.get("sha256"),
            "content_type": record.get("content_type"),
            "status_code": meta.get("status_code") or meta.get("http_status"),
        }

    for node in nodes:
        node_id = str(node.get("id"))
        data = node.get("data") if isinstance(node.get("data"), dict) else {}
        refs = [str(value) for value in [data.get("raw_evidence_ref"), data.get("evidence_id")] if value]
        refs.extend(str(item.get("raw_evidence_ref")) for item in data.get("signals", []) if isinstance(item, dict) and item.get("raw_evidence_ref"))
        records = [compact(evidence_by_id[ref]) for ref in refs if ref in evidence_by_id]
        if records:
            node_map[node_id] = records
        else:
            unsupported.append({"kind": "node", "id": node_id, "label": node.get("label"), "warning": "finding unsupported: no evidence_id/raw_evidence_ref linked"})
    for edge in edges:
        edge_id = str(edge.get("id"))
        data = edge.get("data") if isinstance(edge.get("data"), dict) else {}
        refs = [str(value) for value in [data.get("raw_evidence_ref"), data.get("evidence_id")] if value]
        records = [compact(evidence_by_id[ref]) for ref in refs if ref in evidence_by_id]
        if records:
            edge_map[edge_id] = records
        else:
            unsupported.append({"kind": "edge", "id": edge_id, "label": edge.get("type"), "warning": "relationship unsupported: no evidence_id/raw_evidence_ref linked"})
    return {
        "node_evidence": node_map,
        "edge_evidence": edge_map,
        "unsupported_findings": unsupported,
        "evidence_count": len(evidence),
        "coverage": {"supported_nodes": len(node_map), "supported_edges": len(edge_map), "unsupported": len(unsupported)},
    }


def _score_freshness(fetched_at: Any) -> tuple[int, str]:
    raw = str(fetched_at or "")
    if not raw or raw == "not_available":
        return 20, "missing timestamp"
    return 85, "timestamp present"


def _score_reliability(source: Any, source_url: Any) -> tuple[int, str]:
    text = f"{source} {source_url}".lower()
    if any(marker in text for marker in ("github", "hibp", "rdap", "dns:", "crt.sh", "google", "urlscan")):
        return 85, "public or official source family"
    if source_url:
        return 70, "source URL present"
    return 35, "source URL missing"


def _score_directness(record: dict[str, Any]) -> tuple[int, str]:
    meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
    if meta.get("source_url") or str(record.get("uri") or "").startswith(("http", "dns:")):
        return 80, "direct source reference available"
    if record.get("entity_id"):
        return 55, "linked to entity but source reference is weak"
    return 30, "not directly linked to a finding"


def evidence_quality_report(graph: dict[str, Any], evidence: list[dict[str, Any]]) -> dict[str, Any]:
    evidence_map = build_evidence_map(graph, evidence)
    rows = []
    report_safe = 0
    for record in evidence:
        meta = record.get("meta") if isinstance(record.get("meta"), dict) else {}
        source_url = meta.get("source_url") or record.get("uri")
        freshness, freshness_reason = _score_freshness(meta.get("fetched_at") or record.get("created_at"))
        reliability, reliability_reason = _score_reliability(record.get("source"), source_url)
        directness, directness_reason = _score_directness(record)
        verification = bool(record.get("sha256"))
        quality = int((freshness * 0.2) + (reliability * 0.35) + (directness * 0.3) + ((90 if verification else 20) * 0.15))
        safe = quality >= 65 and bool(record.get("sha256")) and bool(source_url)
        if safe:
            report_safe += 1
        rows.append({
            "evidence_id": record.get("id"),
            "quality_score": quality,
            "freshness_score": freshness,
            "source_reliability_score": reliability,
            "directness_score": directness,
            "report_safe": safe,
            "contradiction_flags": meta.get("contradiction_flags") or [],
            "reasons": [freshness_reason, reliability_reason, directness_reason],
            "source_url": source_url,
            "sha256": record.get("sha256"),
        })
    return {
        "items": rows,
        "summary": {
            "evidence_count": len(evidence),
            "report_safe_count": report_safe,
            "unsupported_findings": len(evidence_map.get("unsupported_findings") or []),
            "average_quality": int(sum(item["quality_score"] for item in rows) / len(rows)) if rows else 0,
        },
        "evidence_map": evidence_map,
    }


def redact_preview(record: Any, terms: list[str] | None = None, limit: int = 5000) -> dict[str, Any]:
    text, truncated = _read_text(str(record.uri), limit)
    redactions = terms or []
    redacted = text
    for term in redactions:
        if term:
            redacted = redacted.replace(term, "[REDACTED]")
    return {
        "evidence_id": record.id,
        "redacted_excerpt": redacted,
        "redaction_terms": redactions,
        "truncated": truncated,
        "note": "Preview only; original evidence hash and payload are unchanged.",
    }
