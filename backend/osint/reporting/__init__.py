from __future__ import annotations

from html import escape
from typing import Any


def build_html_report(*, title: str, graph: dict[str, Any], evidence: list[dict[str, Any]]) -> str:
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    evidence_rows = "".join(
        f"<tr><td>{escape(str(item.get('source', '')))}</td><td>{escape(str(item.get('sha256', '')))}</td><td>{escape(str(item.get('created_at', '')))}</td></tr>"
        for item in evidence
    )
    node_rows = "".join(
        f"<tr><td>{escape(str(node.get('type', '')))}</td><td>{escape(str(node.get('label', '')))}</td><td>{escape(str((node.get('data') or {}).get('confidence_reason', node.get('confidence', ''))))}</td></tr>"
        for node in nodes
    )
    return (
        "<!doctype html>"
        "<html><head><meta charset=\"utf-8\"><title>" + escape(title) + "</title>"
        "<style>body{background:#000;color:#fff;font-family:Inter,Arial,sans-serif}"
        "table{border-collapse:collapse;width:100%}td,th{border:1px solid #333;padding:6px;font-family:monospace}</style></head>"
        "<body><h1>" + escape(title) + "</h1><p>Entities: " + str(len(nodes)) + " / Relationships: " + str(len(edges)) + "</p>"
        "<h2>Findings</h2><table><tbody>" + node_rows + "</tbody></table>"
        "<h2>Evidence Table</h2><table><tbody>" + evidence_rows + "</tbody></table>"
        "</body></html>"
    )
