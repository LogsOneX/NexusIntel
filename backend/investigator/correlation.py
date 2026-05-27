from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any


FEATURES = {
    "shared_avatar_hash": ("same_asset_reuse", 30, ["avatar_hash", "image_hash"]),
    "shared_favicon_hash": ("same_asset_reuse", 28, ["favicon_hash", "mmh3", "favicon_mmh3"]),
    "shared_username": ("possible_same_actor", 22, ["username", "handle", "login"]),
    "shared_external_link": ("possible_same_actor", 24, ["external_link", "website", "url", "source_url"]),
    "shared_email_domain": ("same_operator_hypothesis", 18, ["domain", "mx_domain", "email_domain"]),
    "shared_display_name": ("possible_same_actor", 12, ["display_name", "name", "title"]),
    "shared_bio_phrase": ("possible_same_actor", 14, ["bio", "description"]),
    "shared_location_text": ("possible_same_actor", 10, ["location", "city", "country"]),
    "shared_analytics_id": ("same_infrastructure", 30, ["analytics_id", "ga_id", "gtm_id"]),
    "shared_certificate": ("same_infrastructure", 32, ["certificate_fingerprint", "tls_fingerprint", "cert_sha256"]),
    "shared_infrastructure": ("same_infrastructure", 20, ["ip", "asn", "nameserver", "mx"]),
}


def _data(node: dict[str, Any]) -> dict[str, Any]:
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    artifact = data.get("artifact") if isinstance(data.get("artifact"), dict) else {}
    return {**artifact, **data, "label": node.get("label"), "value": node.get("value")}


def _values(node: dict[str, Any], fields: list[str]) -> set[str]:
    data = _data(node)
    values: set[str] = set()
    for field in fields:
        raw = data.get(field)
        if isinstance(raw, str) and raw.strip():
            values.add(raw.strip().lower())
        elif isinstance(raw, list):
            values.update(str(item).strip().lower() for item in raw if str(item).strip())
    node_type = str(node.get("type") or "").lower()
    value = str(node.get("value") or "").lower().strip()
    if "username" in fields and node_type == "username":
        values.add(value.lstrip("@"))
    if "email_domain" in fields and node_type == "email" and "@" in value:
        values.add(value.split("@", 1)[1])
    if "domain" in fields and node_type == "domain":
        values.add(value)
    if "ip" in fields and node_type == "ip":
        values.add(value)
    return values


def _timestamp(node: dict[str, Any]) -> datetime | None:
    raw = str(_data(node).get("fetched_at") or node.get("created_at") or "")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


class AdvancedCorrelationEngine:
    def correlate(self, graph: dict[str, Any], evidence_map: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        nodes = [node for node in graph.get("nodes") or [] if str(node.get("type") or "").lower() not in {"guardrail", "legal_note", "compliance", "noise"}]
        correlations: list[dict[str, Any]] = []
        for index, left in enumerate(nodes):
            for right in nodes[index + 1:]:
                score = 0
                reasons: list[str] = []
                relation_votes: dict[str, int] = {}
                shared: dict[str, list[str]] = {}
                for feature, (relation, weight, fields) in FEATURES.items():
                    overlap = _values(left, fields) & _values(right, fields)
                    if overlap:
                        score += weight
                        relation_votes[relation] = relation_votes.get(relation, 0) + weight
                        shared[feature] = sorted(overlap)[:6]
                        reasons.append(f"{feature}: {', '.join(sorted(overlap)[:3])}")
                left_time = _timestamp(left)
                right_time = _timestamp(right)
                if left_time and right_time:
                    delta_days = abs((left_time - right_time).days)
                    if delta_days <= 7:
                        score += 6
                        reasons.append("temporal proximity within 7 days")
                left_loc = _values(left, ["location", "city", "country"])
                right_loc = _values(right, ["location", "city", "country"])
                if left_loc and right_loc and not (left_loc & right_loc):
                    score -= 12
                    reasons.append("contradiction penalty: conflicting location text")
                if score < 35:
                    continue
                relation = max(relation_votes.items(), key=lambda item: item[1])[0] if relation_votes else "possible_same_actor"
                confidence = max(0, min(89, score))
                cid = hashlib.sha256(f"{left.get('id')}:{right.get('id')}:{shared}".encode()).hexdigest()[:16]
                node_evidence = (evidence_map or {}).get("node_evidence", {})
                supporting = list(node_evidence.get(str(left.get("id")), [])) + list(node_evidence.get(str(right.get("id")), []))
                correlations.append({
                    "correlation_id": cid,
                    "type": relation,
                    "source": left.get("id"),
                    "target": right.get("id"),
                    "score": confidence,
                    "confidence_level": confidence,
                    "reasons": reasons,
                    "shared_features": shared,
                    "supporting_evidence": supporting[:12],
                    "contradicting_evidence": [reason for reason in reasons if "contradiction" in reason.lower()],
                    "requires_analyst_confirmation": True,
                    "recommended_next_tests": ["Collect direct evidence for both nodes", "Validate shared artifact uniqueness", "Review contradictions before confirming edge"],
                    "score_breakdown": {"base_score": score, "clamped_confidence": confidence, "shared_features": shared},
                    "legal_basis": "Derived from public-source evidence metadata and local deterministic correlation; not an attribution claim.",
                })
        return sorted(correlations, key=lambda item: item["score"], reverse=True)
