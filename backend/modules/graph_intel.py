from __future__ import annotations

import re
from collections import Counter, defaultdict, deque
from typing import Any

SUSPICIOUS_DOMAIN_TERMS = ("login-", "secure-", "verify-", "account-", "wallet-", "signin-", "-login", "-verify", "password", "update-billing")
SOURCE_WEIGHTS = {
    "investigator": 96,
    "manual": 92,
    "nexusrecon": 74,
    "ghost_identity": 78,
    "identity_recon": 66,
    "email_recon": 72,
    "ghost_email": 76,
    "network_recon": 82,
    "domain_recon": 82,
    "phone_recon": 70,
    "ghost_phone": 68,
    "cascade_correlation": 60,
}
CONFIDENCE_WEIGHTS = {
    "confirmed": 95,
    "exact": 95,
    "high": 86,
    "success": 86,
    "medium": 62,
    "observed": 58,
    "probable": 58,
    "low": 32,
    "candidate": 28,
    "weak": 22,
    "unknown": 38,
}


def _data(item: dict[str, Any]) -> dict[str, Any]:
    data = item.get("data") if isinstance(item.get("data"), dict) else item.get("nodeProperties") if isinstance(item.get("nodeProperties"), dict) else {}
    return data if isinstance(data, dict) else {}


def _node_id(node: dict[str, Any]) -> str:
    return str(node.get("id") or "")


def _node_type(node: dict[str, Any]) -> str:
    return str(node.get("type") or node.get("nodeType") or "unknown").lower()


def _label(node: dict[str, Any]) -> str:
    return str(node.get("label") or node.get("nodeLabel") or node.get("value") or node.get("id") or "unknown")


def _value(node: dict[str, Any]) -> str:
    return str(node.get("value") or _data(node).get("value") or _label(node))


def _confidence(node: dict[str, Any]) -> str:
    return str(node.get("confidence") or _data(node).get("confidence") or "medium").lower()


def _source(node: dict[str, Any]) -> str:
    return str(node.get("source") or _data(node).get("source") or "unknown").lower()


def _confidence_score(value: str) -> int:
    return CONFIDENCE_WEIGHTS.get(value.lower(), 50)


def _source_score(value: str) -> int:
    return SOURCE_WEIGHTS.get(value.lower(), 48)


def _private_ip(value: str) -> bool:
    ip = value.strip().lower()
    return bool(
        re.match(r"^(10|127|0)\.", ip)
        or re.match(r"^192\.168\.", ip)
        or re.match(r"^172\.(1[6-9]|2\d|3[01])\.", ip)
        or re.match(r"^169\.254\.", ip)
        or re.match(r"^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.", ip)
        or ip == "::1"
        or ip.startswith(("fc", "fd", "fe80:"))
    )


def _suspicious_domain(value: str) -> bool:
    lowered = value.lower()
    return any(term in lowered for term in SUSPICIOUS_DOMAIN_TERMS)


def _connected_components(node_ids: set[str], adjacency: dict[str, set[str]]) -> list[list[str]]:
    seen: set[str] = set()
    components: list[list[str]] = []
    for node_id in node_ids:
        if node_id in seen:
            continue
        group: list[str] = []
        queue: deque[str] = deque([node_id])
        seen.add(node_id)
        while queue:
            current = queue.popleft()
            group.append(current)
            for neighbor in adjacency.get(current, set()):
                if neighbor not in seen:
                    seen.add(neighbor)
                    queue.append(neighbor)
        components.append(group)
    components.sort(key=len, reverse=True)
    return components


def build_graph_intelligence(graph_state: dict[str, Any]) -> dict[str, Any]:
    nodes = [item for item in graph_state.get("nodes", []) if isinstance(item, dict) and _node_id(item)]
    edges = [item for item in graph_state.get("edges", []) if isinstance(item, dict)]
    by_id = {_node_id(node): node for node in nodes}
    degree: Counter[str] = Counter()
    adjacency: dict[str, set[str]] = defaultdict(set)
    edge_types: Counter[str] = Counter()
    for edge in edges:
        source = str(edge.get("source") or edge.get("source_id") or "")
        target = str(edge.get("target") or edge.get("target_id") or "")
        if source and target:
            degree[source] += 1
            degree[target] += 1
            adjacency[source].add(target)
            adjacency[target].add(source)
        edge_types[str(edge.get("type") or edge.get("label") or "RELATED_TO").upper()] += 1

    source_scores = [_source_score(_source(node)) for node in nodes]
    confidence_scores = [_confidence_score(_confidence(node)) for node in nodes]
    reliability = int(round((sum(source_scores) + sum(confidence_scores)) / max(1, len(source_scores) + len(confidence_scores))))

    entity_risks: list[dict[str, Any]] = []
    leads: list[dict[str, Any]] = []
    for node in nodes:
        node_id = _node_id(node)
        node_type = _node_type(node)
        value = _value(node)
        confidence = _confidence(node)
        score = 0
        tags: list[str] = []
        if confidence in {"low", "weak", "candidate"}:
            score += 12
            tags.append("VERIFY")
        if degree[node_id] > 10:
            score += 25
            tags.append("CORE_HUB")
        elif degree[node_id] > 5:
            score += 14
            tags.append("PIVOT_HUB")
        if node_type == "ip" and _private_ip(value):
            score += 18
            tags.append("INTERNAL")
        if node_type == "domain" and _suspicious_domain(value):
            score += 30
            tags.append("SUSPICIOUS_DOMAIN")
        if node_type == "email" and confidence in {"confirmed", "high"} and not any(_node_type(by_id.get(edge.get("target"), {})) == "domain" for edge in edges if edge.get("source") == node_id):
            score += 10
            tags.append("EXPAND_MAILBOX")
        if tags:
            entity_risks.append({"id": node_id, "type": node_type, "label": _label(node), "value": value, "score": min(100, score), "tags": tags, "degree": int(degree[node_id])})

        if node_type in {"username", "email"} and degree[node_id] < 3:
            leads.append({"priority": "high", "node_id": node_id, "label": _label(node), "action": "tier_1_major_socials", "reason": "Start with a fast clustered identity sweep before deep enumeration."})
        if node_type == "domain" and not any(str(edge.get("source")) == node_id and str(edge.get("type", "")).lower() in {"resolves_to", "has_dns_record", "hosted_by_domain"} for edge in edges):
            leads.append({"priority": "high", "node_id": node_id, "label": _label(node), "action": "domain_recon", "reason": "Domain exists without DNS/IP expansion."})
        if node_type == "ip" and degree[node_id] <= 1:
            leads.append({"priority": "medium", "node_id": node_id, "label": _label(node), "action": "reverse_dns", "reason": "IP node is thin; reverse DNS/RDAP may reveal infrastructure context."})

    entity_risks.sort(key=lambda item: (item["score"], item["degree"]), reverse=True)
    leads.sort(key=lambda item: {"high": 3, "medium": 2, "low": 1}.get(str(item["priority"]), 0), reverse=True)

    components = _connected_components(set(by_id), adjacency)
    communities = []
    for index, component in enumerate(components[:8], start=1):
        type_mix = Counter(_node_type(by_id[node_id]) for node_id in component if node_id in by_id)
        hub_id = max(component, key=lambda item: degree[item]) if component else ""
        communities.append({
            "id": f"cluster_{index}",
            "size": len(component),
            "hub_id": hub_id,
            "hub_label": _label(by_id[hub_id]) if hub_id in by_id else "unknown",
            "types": dict(type_mix),
        })

    top_sources = Counter(_source(node) for node in nodes).most_common(8)
    dossier = {
        "root": _label(nodes[0]) if nodes else "empty",
        "entity_count": len(nodes),
        "relationship_count": len(edges),
        "top_entity_types": Counter(_node_type(node) for node in nodes).most_common(8),
        "top_relationships": edge_types.most_common(8),
        "top_sources": top_sources,
        "core_entities": entity_risks[:8],
    }

    risk_score = min(100, max(0, int(round((100 - reliability) * 0.35 + sum(item["score"] for item in entity_risks[:8]) / 8)))) if nodes else 0
    posture = "critical" if risk_score >= 75 else "watch" if risk_score >= 45 else "stable" if nodes else "empty"

    return {
        "posture": posture,
        "risk_score": risk_score,
        "source_reliability": reliability,
        "lead_queue": leads[:12],
        "entity_risks": entity_risks[:25],
        "communities": communities,
        "dossier": dossier,
    }
