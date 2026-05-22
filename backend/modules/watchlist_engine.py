from __future__ import annotations

import hashlib
import json
from typing import Any


def graph_signature(graph: dict[str, Any]) -> str:
    stable = {
        "nodes": sorted([{"type": n.get("type"), "value": n.get("value")} for n in graph.get("nodes", []) if isinstance(n, dict)], key=lambda x: (str(x.get("type")), str(x.get("value")))) ,
        "edges": sorted([{"source": e.get("source"), "target": e.get("target"), "type": e.get("type")} for e in graph.get("edges", []) if isinstance(e, dict)], key=lambda x: (str(x.get("source")), str(x.get("target")), str(x.get("type")))) ,
    }
    return hashlib.sha256(json.dumps(stable, sort_keys=True).encode()).hexdigest()


def diff_graph(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    if not previous:
        return {"changed": True, "new_nodes": len(current.get("nodes", [])), "new_edges": len(current.get("edges", [])), "removed_nodes": 0, "removed_edges": 0}
    prev_nodes = {str(n.get("id")) for n in previous.get("nodes", []) if isinstance(n, dict)}
    curr_nodes = {str(n.get("id")) for n in current.get("nodes", []) if isinstance(n, dict)}
    prev_edges = {str(e.get("id")) for e in previous.get("edges", []) if isinstance(e, dict)}
    curr_edges = {str(e.get("id")) for e in current.get("edges", []) if isinstance(e, dict)}
    return {
        "changed": prev_nodes != curr_nodes or prev_edges != curr_edges,
        "new_nodes": len(curr_nodes - prev_nodes),
        "new_edges": len(curr_edges - prev_edges),
        "removed_nodes": len(prev_nodes - curr_nodes),
        "removed_edges": len(prev_edges - curr_edges),
    }
