from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from backend.investigator.noise_killer import NoiseKiller
from backend.investigator.types import EvidenceCitation


def _data(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("data") if isinstance(item.get("data"), dict) else {}


def _artifact(item: dict[str, Any]) -> dict[str, Any]:
    data = _data(item)
    return data.get("artifact") if isinstance(data.get("artifact"), dict) else {}


def _confidence(item: dict[str, Any]) -> int:
    data = _data(item)
    artifact = _artifact(item)
    for value in (item.get("confidence_score"), item.get("confidence_level"), data.get("confidence_score"), artifact.get("confidence_score")):
        if isinstance(value, (int, float)):
            return max(0, min(100, int(value)))
    raw = str(item.get("confidence") or data.get("confidence") or "medium").lower()
    return {"confirmed": 95, "high": 85, "probable": 70, "medium": 60, "weak": 42, "candidate": 35, "low": 25, "noise": 10}.get(raw, 45)


def _source_url(item: dict[str, Any]) -> str | None:
    data = _data(item)
    artifact = _artifact(item)
    value = item.get("source_url") or data.get("source_url") or artifact.get("source_url") or data.get("final_url")
    return str(value) if value else None


def _raw_ref(item: dict[str, Any]) -> str | None:
    data = _data(item)
    artifact = _artifact(item)
    value = data.get("raw_evidence_ref") or artifact.get("raw_evidence_ref") or data.get("evidence_id") or item.get("raw_evidence_ref")
    return str(value) if value else None


def _timestamp(item: dict[str, Any]) -> str | None:
    data = _data(item)
    artifact = _artifact(item)
    value = item.get("fetched_at") or data.get("fetched_at") or artifact.get("fetched_at") or item.get("created_at")
    return str(value) if value else None


def _freshness(value: str | None) -> int:
    if not value:
        return 30
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        age_days = max(0, (datetime.now(timezone.utc) - parsed.astimezone(timezone.utc)).days)
    except Exception:
        return 45
    if age_days <= 7:
        return 100
    if age_days <= 30:
        return 85
    if age_days <= 180:
        return 65
    if age_days <= 730:
        return 45
    return 25


def _source_reliability(source: str) -> int:
    raw = source.lower()
    if any(marker in raw for marker in ("official", "rdap", "dns", "ct", "github", "hibp", "urlscan", "virustotal")):
        return 85
    if any(marker in raw for marker in ("public", "web", "profile", "gravatar")):
        return 72
    if "analyst" in raw:
        return 55
    if "manual" in raw or "investigator" in raw:
        return 50
    if "legacy" in raw or "scanner" in raw:
        return 48
    return 40


class EvidenceReasoner:
    def __init__(self) -> None:
        self.noise = NoiseKiller()

    def citation_for_node(self, node: dict[str, Any], evidence_records: list[dict[str, Any]]) -> list[EvidenceCitation]:
        refs: list[EvidenceCitation] = []
        raw_ref = _raw_ref(node)
        if raw_ref:
            match = next((item for item in evidence_records if str(item.get("id")) == raw_ref), None)
            refs.append(EvidenceCitation(raw_ref, str(match.get("source") if match else node.get("source") or "unknown"), str(match.get("uri") if match else _source_url(node) or "") or None, str(match.get("sha256") if match else _data(node).get("payload_sha256") or "") or None, str(match.get("created_at") if match else _timestamp(node) or "") or None))
        return refs

    def reason(self, graph: dict[str, Any], evidence_records: list[dict[str, Any]], selected_entity_id: str | None = None) -> dict[str, Any]:
        nodes = graph.get("nodes") or []
        edges = graph.get("edges") or []
        node_map: dict[str, dict[str, Any]] = {}
        missing: list[dict[str, Any]] = []
        contradictions: list[dict[str, Any]] = []
        for node in nodes:
            node_id = str(node.get("id"))
            citations = self.citation_for_node(node, evidence_records)
            noise_decision = self.noise.decide(node)
            source_url = _source_url(node)
            raw_ref = _raw_ref(node)
            timestamp = _timestamp(node)
            directness = 95 if source_url and raw_ref else 70 if source_url or raw_ref else 35
            corroboration = min(100, 25 + len(citations) * 35 + len([edge for edge in edges if edge.get("source") == node_id or edge.get("target") == node_id]) * 5)
            source = str(node.get("source") or _data(node).get("source") or "unknown")
            score = max(0, min(100, int((_confidence(node) * 0.36) + (_source_reliability(source) * 0.2) + (directness * 0.18) + (_freshness(timestamp) * 0.12) + (corroboration * 0.14) - noise_decision.noise_score * 0.35)))
            flags: list[str] = []
            if not source_url:
                flags.append("missing source_url")
            if not raw_ref:
                flags.append("missing raw_evidence_ref")
            if not timestamp:
                flags.append("missing timestamp")
            if noise_decision.is_noise:
                flags.append("noise assessment active")
            if any("not found" in reason.lower() or "soft 404" in reason.lower() for reason in noise_decision.reasons):
                contradictions.append({"node_id": node_id, "label": node.get("label"), "reason": "source indicates not found / soft 404"})
            if flags:
                missing.append({"node_id": node_id, "label": node.get("label"), "warnings": flags})
            node_map[node_id] = {
                "node_id": node_id,
                "label": node.get("label"),
                "type": node.get("type"),
                "final_confidence": score,
                "source_reliability": _source_reliability(source),
                "evidence_directness": directness,
                "freshness": _freshness(timestamp),
                "corroboration": corroboration,
                "noise_penalty": noise_decision.noise_score,
                "evidence_refs": [ref.to_dict() for ref in citations],
                "warnings": flags,
                "status": "verified" if score >= 80 and not flags and not noise_decision.is_noise else "weak" if score >= 40 else "insufficient_evidence",
            }
        edge_map = {str(edge.get("id")): {"edge_id": edge.get("id"), "type": edge.get("type"), "source": edge.get("source"), "target": edge.get("target"), "confidence_level": edge.get("confidence_level") or _data(edge).get("confidence_level") or 50, "evidence_refs": []} for edge in edges}
        return {
            "selected_entity_id": selected_entity_id,
            "node_evidence": node_map,
            "edge_evidence": edge_map,
            "missing_evidence_warnings": missing,
            "contradiction_flags": contradictions,
            "evidence_count": len(evidence_records),
        }
