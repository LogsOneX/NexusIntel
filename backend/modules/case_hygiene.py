from __future__ import annotations

from collections import Counter
from typing import Any

IMPORTANT_TYPES = {"username", "email", "domain", "ip", "phone", "profile", "service", "platform"}
WEAK_CONFIDENCE = {"low", "weak", "candidate", "unknown"}
STRONG_CONFIDENCE = {"confirmed", "exact", "high", "success"}


def _node_type(node: dict[str, Any]) -> str:
    return str(node.get("type") or node.get("nodeType") or "unknown").lower()


def _node_label(node: dict[str, Any]) -> str:
    return str(node.get("label") or node.get("nodeLabel") or node.get("value") or node.get("id") or "unknown")


def _node_confidence(node: dict[str, Any]) -> str:
    data = node.get("data") if isinstance(node.get("data"), dict) else node.get("nodeProperties") if isinstance(node.get("nodeProperties"), dict) else {}
    return str(node.get("confidence") or data.get("confidence") or "medium").lower()


def build_case_hygiene_report(graph_state: dict[str, Any]) -> dict[str, Any]:
    nodes = [item for item in graph_state.get("nodes", []) if isinstance(item, dict)]
    edges = [item for item in graph_state.get("edges", []) if isinstance(item, dict)]
    by_type = Counter(_node_type(node) for node in nodes)
    by_confidence = Counter(_node_confidence(node) for node in nodes)

    linked_ids: set[str] = set()
    edge_types: Counter[str] = Counter()
    for edge in edges:
        source = str(edge.get("source") or edge.get("source_id") or "")
        target = str(edge.get("target") or edge.get("target_id") or "")
        if source:
            linked_ids.add(source)
        if target:
            linked_ids.add(target)
        edge_types[str(edge.get("type") or edge.get("label") or "RELATED_TO").upper()] += 1

    weak_nodes = [
        {"id": node.get("id"), "type": _node_type(node), "label": _node_label(node), "confidence": _node_confidence(node)}
        for node in nodes
        if _node_confidence(node) in WEAK_CONFIDENCE
    ]
    isolated_nodes = [
        {"id": node.get("id"), "type": _node_type(node), "label": _node_label(node)}
        for node in nodes
        if str(node.get("id") or "") not in linked_ids and _node_type(node) not in {"target", "case"}
    ]

    recommendations: list[dict[str, str]] = []
    if by_type.get("username", 0) and by_type.get("profile", 0) == 0:
        recommendations.append({"priority": "high", "action": "maigret_username", "reason": "Username pivots exist but no confirmed public profiles are linked."})
    if by_type.get("email", 0) and by_type.get("domain", 0) == 0:
        recommendations.append({"priority": "high", "action": "email_footprint", "reason": "Email pivots exist but mailbox/domain posture has not been expanded."})
    if by_type.get("domain", 0) and by_type.get("ip", 0) == 0:
        recommendations.append({"priority": "high", "action": "domain_recon", "reason": "Domain nodes exist but no IP/DNS resolution has been collected."})
    if by_type.get("phone", 0) and by_type.get("service", 0) == 0:
        recommendations.append({"priority": "medium", "action": "phone_recon", "reason": "Phone pivots exist but numbering-plan/service context is thin."})
    if len(weak_nodes) > 5:
        recommendations.append({"priority": "medium", "action": "verify_weak_nodes", "reason": f"{len(weak_nodes)} weak-confidence entities need confirmation or removal."})
    if len(isolated_nodes) > 3:
        recommendations.append({"priority": "low", "action": "link_or_prune_isolated", "reason": f"{len(isolated_nodes)} isolated entities are not connected to the investigation chain."})
    if not recommendations and nodes:
        recommendations.append({"priority": "low", "action": "export_report", "reason": "Graph hygiene looks stable enough for a snapshot report."})
    if not nodes:
        recommendations.append({"priority": "high", "action": "create_or_launch_investigation", "reason": "No graph entities are loaded. Create a blank case or launch a target scan."})

    coverage = {key: int(by_type.get(key, 0)) for key in sorted(IMPORTANT_TYPES)}
    strong_count = sum(count for confidence, count in by_confidence.items() if confidence in STRONG_CONFIDENCE)
    weak_count = len(weak_nodes)
    total = max(1, len(nodes))
    relationship_factor = min(25, len(edges) * 3)
    coverage_factor = min(35, len([kind for kind, count in coverage.items() if count]) * 5)
    confidence_factor = int((strong_count / total) * 30) - min(18, weak_count * 2)
    isolation_penalty = min(18, len(isolated_nodes) * 2)
    score = max(0, min(100, 20 + relationship_factor + coverage_factor + confidence_factor - isolation_penalty))

    if score >= 78:
        status = "operational"
    elif score >= 52:
        status = "developing"
    elif nodes:
        status = "thin"
    else:
        status = "empty"

    return {
        "score": score,
        "status": status,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "coverage": coverage,
        "by_type": dict(by_type),
        "by_confidence": dict(by_confidence),
        "edge_types": dict(edge_types),
        "weak_nodes": weak_nodes[:50],
        "isolated_nodes": isolated_nodes[:50],
        "recommendations": recommendations[:8],
    }
