from __future__ import annotations

import hashlib
from typing import Any

from backend.investigator.types import EvidenceCitation, Hypothesis, HypothesisStatus


def _features(node: dict[str, Any]) -> dict[str, set[str]]:
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    artifact = data.get("artifact") if isinstance(data.get("artifact"), dict) else {}
    combined = {**artifact, **data, "value": node.get("value"), "label": node.get("label")}
    keys = {
        "avatar_hash": ["avatar_hash", "image_hash", "favicon_hash", "email_hash_md5"],
        "username": ["username", "handle", "login"],
        "external_link": ["external_link", "website", "url", "source_url"],
        "domain_email": ["domain", "email", "mx_domain"],
        "display_name": ["display_name", "name", "title"],
        "location_text": ["location", "city", "country"],
    }
    result: dict[str, set[str]] = {key: set() for key in keys}
    for feature, fields in keys.items():
        for field in fields:
            value = combined.get(field)
            if isinstance(value, str) and value.strip():
                result[feature].add(value.strip().lower())
            elif isinstance(value, list):
                result[feature].update(str(item).strip().lower() for item in value if str(item).strip())
    node_type = str(node.get("type") or "").lower()
    raw_value = str(node.get("value") or "").lower()
    if node_type == "username":
        result["username"].add(raw_value.lstrip("@"))
    if node_type == "email" and "@" in raw_value:
        local, domain = raw_value.split("@", 1)
        result["username"].add(local)
        result["domain_email"].add(domain)
    if node_type == "domain":
        result["domain_email"].add(raw_value)
    return result


class HypothesisEngine:
    def generate(self, graph: dict[str, Any], validation: dict[str, Any]) -> list[Hypothesis]:
        nodes = graph.get("nodes") or []
        by_id = {str(node.get("id")): node for node in nodes}
        features = {node_id: _features(node) for node_id, node in by_id.items()}
        hypotheses: list[Hypothesis] = []
        ids = list(by_id)
        for index, left_id in enumerate(ids):
            for right_id in ids[index + 1:]:
                shared: dict[str, list[str]] = {}
                score = 0
                for feature, values in features[left_id].items():
                    overlap = values & features[right_id].get(feature, set())
                    if overlap:
                        shared[feature] = sorted(overlap)[:5]
                        score += {"avatar_hash": 42, "external_link": 25, "domain_email": 30, "username": 24, "display_name": 14, "location_text": 12}.get(feature, 10)
                if score < 45:
                    continue
                confidence = min(89, score)
                status = HypothesisStatus.SUPPORTED if confidence >= 70 else HypothesisStatus.PROPOSED
                statement = f"{by_id[left_id].get('label')} and {by_id[right_id].get('label')} may describe related operator-controlled assets."
                warning = "Analyst review required; below 90 remains a hypothesis, not identity attribution."
                hypothesis_id = hashlib.sha256(f"{left_id}:{right_id}:{shared}".encode()).hexdigest()[:16]
                hypotheses.append(Hypothesis(hypothesis_id, statement, status, [], [], confidence, f"Shared features: {shared}", ["Collect direct public source evidence for both entities", "Check for contradiction markers and independent corroboration"], ["profile_to_links", "avatar_to_hashes"], warning))
        for node in nodes:
            if str(node.get("type") or "").lower() == "domain" and any(term in str(node.get("value") or node.get("label") or "").lower() for term in ("login", "secure", "verify", "account")):
                hid = hashlib.sha256(str(node.get("id")).encode()).hexdigest()[:16]
                hypotheses.append(Hypothesis(hid, f"{node.get('label')} may be an impersonation or phishing-lookalike candidate.", HypothesisStatus.PROPOSED, [], [], 58, "Suspicious keyword in domain; needs DNS/RDAP/CT/favicon corroboration.", ["Compare with official domain", "Collect RDAP, DNS, CT, favicon hash, and web fingerprint"], ["domain_to_dns", "domain_to_rdap", "domain_to_ct_subdomains", "domain_to_favicon_hash"], "Do not report as malicious without corroborated infrastructure evidence."))
        return hypotheses
