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
