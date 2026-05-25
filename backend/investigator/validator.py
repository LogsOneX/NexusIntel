from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlparse

from backend.investigator.evidence_reasoner import EvidenceReasoner
from backend.investigator.noise_killer import NoiseKiller
from backend.investigator.types import ValidationResult

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
DOMAIN_RE = re.compile(r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I)
PHONE_RE = re.compile(r"^\+[1-9]\d{7,14}$")
HASH_RE = re.compile(r"^(?:[a-f0-9]{32}|[a-f0-9]{40}|[a-f0-9]{64})$", re.I)


def syntax_ok(kind: str, value: str) -> bool:
    raw = value.strip()
    if kind == "email":
        return bool(EMAIL_RE.match(raw))
    if kind == "domain":
        return bool(DOMAIN_RE.match(raw.replace("http://", "").replace("https://", "").split("/")[0]))
    if kind == "ip":
        try:
            ipaddress.ip_address(raw)
            return True
        except ValueError:
            return False
    if kind == "phone":
        return bool(PHONE_RE.match(raw.replace(" ", "").replace("-", "")))
    if kind in {"url", "profile", "public_profile"}:
        parsed = urlparse(raw)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)
    if "hash" in kind:
        return bool(HASH_RE.match(raw))
    return bool(raw)


class Validator:
    def __init__(self) -> None:
        self.reasoner = EvidenceReasoner()
        self.noise = NoiseKiller()

    def validate_node(self, node: dict[str, Any], graph: dict[str, Any], evidence_records: list[dict[str, Any]]) -> ValidationResult:
        node_id = str(node.get("id") or "")
        reasoned = self.reasoner.reason({"nodes": [node], "edges": [edge for edge in graph.get("edges", []) if edge.get("source") == node_id or edge.get("target") == node_id]}, evidence_records, node_id)
        row = reasoned["node_evidence"].get(node_id, {})
        noise = self.noise.decide(node)
        kind = str(node.get("type") or "unknown").lower()
        value = str(node.get("value") or node.get("label") or "")
        explanation = list(row.get("warnings") or [])
        if not syntax_ok(kind, value):
            explanation.append(f"syntax validation failed for {kind}")
        if noise.is_noise:
            explanation.extend(noise.reasons)
        confidence = int(row.get("final_confidence") or 0)
        if noise.is_noise:
            label = "NOISE"
        elif confidence >= 90 and not explanation:
            label = "VERIFIED"
        elif confidence >= 80:
            label = "STRONG"
        elif confidence >= 65:
            label = "PROBABLE"
        elif confidence >= 45:
            label = "WEAK"
        elif "candidate" in kind:
            label = "CANDIDATE"
        else:
            label = "INSUFFICIENT_EVIDENCE"
        return ValidationResult(node_id or None, str(node.get("label") or value), label, confidence, int(row.get("source_reliability") or 0), int(row.get("evidence_directness") or 0), int(row.get("freshness") or 0), int(row.get("corroboration") or 0), len(reasoned.get("contradiction_flags") or []) * 25, noise.noise_score, explanation or ["validation completed"], [])

    def validate_graph(self, graph: dict[str, Any], evidence_records: list[dict[str, Any]], selected_entity_id: str | None = None) -> dict[str, Any]:
        results = [self.validate_node(node, graph, evidence_records).to_dict() for node in graph.get("nodes", [])]
        counts: dict[str, int] = {}
        for item in results:
            counts[item["validation_label"]] = counts.get(item["validation_label"], 0) + 1
        selected = next((item for item in results if item.get("target_id") == selected_entity_id), None) if selected_entity_id else None
        return {"counts": counts, "results": results, "selected": selected}
