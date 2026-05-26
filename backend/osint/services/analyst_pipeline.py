from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from html import escape
from typing import Any

from backend.osint.registry import registry

COVERAGE_COLUMNS = [
    "Email",
    "Username",
    "Phone",
    "Domain",
    "IP",
    "Image",
    "Google Maps",
    "Breach",
    "Web Search",
    "Infrastructure",
    "Social",
    "Code",
    "Crypto",
]
COVERAGE_ROWS = ["attempted", "found", "verified", "noisy", "disabled", "requires_api_key"]
CONFIDENCE_BASELINE = {
    "confirmed": 95,
    "exact": 95,
    "high": 85,
    "success": 85,
    "probable": 68,
    "medium": 60,
    "observed": 58,
    "weak": 42,
    "candidate": 35,
    "low": 28,
    "noise": 10,
    "unknown": 40,
}
CDN_MARKERS = ("cloudflare", "akamai", "fastly", "cloudfront", "cdn77", "bunnycdn", "googleusercontent", "azureedge", "edgesuite")
REGISTRAR_PRIVACY_MARKERS = ("privacy", "redacted", "whoisguard", "domains by proxy", "identity protect", "contact privacy")
GENERIC_LOGIN_MARKERS = ("login", "sign in", "signup", "register", "forgot password", "reset password")
AUTH_WALL_MARKERS = ("login required", "sign in to continue", "you must be logged in", "authenticate")
PARKED_MARKERS = ("parked", "buy this domain", "domain for sale", "sedo", "afternic", "parkingcrew")
SOFT_404_MARKERS = ("not found", "404", "does not exist", "page unavailable", "user not found", "profile not found")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _data(node: dict[str, Any]) -> dict[str, Any]:
    data = node.get("data") if isinstance(node.get("data"), dict) else {}
    return data


def _node_id(node: dict[str, Any]) -> str:
    return str(node.get("id") or "")


def _node_type(node: dict[str, Any]) -> str:
    return str(node.get("type") or node.get("nodeType") or "unknown").lower()


def _label(node: dict[str, Any]) -> str:
    return str(node.get("label") or node.get("nodeLabel") or node.get("value") or node.get("id") or "unknown")


def _value(node: dict[str, Any]) -> str:
    return str(node.get("value") or _data(node).get("value") or _label(node))


def _source(node: dict[str, Any]) -> str:
    return str(node.get("source") or _data(node).get("source") or _data(node).get("artifact", {}).get("source") or "unknown")


def _confidence_label(node: dict[str, Any]) -> str:
    return str(node.get("confidence") or _data(node).get("confidence") or "unknown").lower()


def _confidence_score(node: dict[str, Any]) -> int:
    data = _data(node)
    artifact = data.get("artifact") if isinstance(data.get("artifact"), dict) else {}
    for value in (data.get("confidence_score"), artifact.get("confidence_score"), node.get("confidence_level")):
        if isinstance(value, (int, float)):
            return max(0, min(100, int(value)))
    return CONFIDENCE_BASELINE.get(_confidence_label(node), 40)


def _source_url(node: dict[str, Any]) -> str:
    data = _data(node)
    artifact = data.get("artifact") if isinstance(data.get("artifact"), dict) else {}
    return str(data.get("source_url") or artifact.get("source_url") or "")


def _text_blob(node: dict[str, Any]) -> str:
    data = _data(node)
    return " ".join([
        _label(node),
        _value(node),
        _source(node),
        _source_url(node),
        json.dumps(data, default=str).lower()[:6000],
    ]).lower()


def _coverage_column_for_type(node_type: str, source: str = "") -> list[str]:
    raw = f"{node_type} {source}".lower()
    columns: list[str] = []
    if "email" in raw or "mx" in raw or "workspace" in raw:
        columns.append("Email")
    if "username" in raw or "profile" in raw or "platform" in raw:
        columns.append("Username")
    if "phone" in raw:
        columns.append("Phone")
    if "domain" in raw or "dns" in raw or "subdomain" in raw:
        columns.append("Domain")
    if node_type == "ip" or "rdap" in raw or "asn" in raw:
        columns.append("IP")
    if "image" in raw or "avatar" in raw or "favicon" in raw:
        columns.append("Image")
    if "maps" in raw or "google_review" in raw or "location" in raw:
        columns.append("Google Maps")
    if "breach" in raw or "hibp" in raw:
        columns.append("Breach")
    if "web" in raw or "url" in raw or "external_link" in raw:
        columns.append("Web Search")
    if "dns" in raw or "rdap" in raw or "ct_" in raw or "infrastructure" in raw or "asn" in raw:
        columns.append("Infrastructure")
    if "social" in raw or "profile" in raw or "username.public" in raw:
        columns.append("Social")
    if "github" in raw or "code" in raw or "gitlab" in raw:
        columns.append("Code")
    if "crypto" in raw or "wallet" in raw or "transaction" in raw:
        columns.append("Crypto")
    return columns or ["Web Search"]


def _empty_matrix() -> dict[str, dict[str, int]]:
    return {row: {column: 0 for column in COVERAGE_COLUMNS} for row in COVERAGE_ROWS}


def build_coverage_matrix(nodes: list[dict[str, Any]], task_records: list[dict[str, Any]], transforms: list[dict[str, Any]]) -> dict[str, Any]:
    matrix = _empty_matrix()
    for transform in transforms:
        for output in transform.get("output_types", []) or []:
            for column in _coverage_column_for_type(str(output), str(transform.get("adapter_id") or "")):
                if transform.get("enabled") is False:
                    matrix["disabled"][column] += 1
                if transform.get("requires_api_key"):
                    matrix["requires_api_key"][column] += 1
    for task in task_records:
        raw = f"{task.get('task_name', '')} {task.get('target', '')}"
        for column in _coverage_column_for_type(raw):
            matrix["attempted"][column] += 1
    for node in nodes:
        node_type = _node_type(node)
        source = _source(node)
        score = _confidence_score(node)
        for column in _coverage_column_for_type(node_type, source):
            matrix["found"][column] += 1
            if score >= 80:
                matrix["verified"][column] += 1
            if score < 40 or assess_noise(node)["is_noise"]:
                matrix["noisy"][column] += 1
    return {"columns": COVERAGE_COLUMNS, "rows": COVERAGE_ROWS, "matrix": matrix}


def assess_noise(node: dict[str, Any]) -> dict[str, Any]:
    node_type = _node_type(node)
    value = _value(node).lower()
    blob = _text_blob(node)
    reasons: list[str] = []
    score = 0
    if node_type == "ip" and any(marker in blob for marker in CDN_MARKERS):
        score += 35
        reasons.append("shared CDN or edge provider infrastructure")
    if node_type in {"domain", "rdap_record", "nameserver"} and any(marker in blob for marker in REGISTRAR_PRIVACY_MARKERS):
        score += 18
        reasons.append("registrar privacy/redacted registration data")
    if any(marker in blob for marker in GENERIC_LOGIN_MARKERS) and node_type in {"public_profile", "profile", "web_fingerprint", "url"}:
        score += 30
        reasons.append("generic login/sign-up page signal")
    if any(marker in blob for marker in AUTH_WALL_MARKERS):
        score += 45
        reasons.append("auth wall only; no public profile evidence")
    if any(marker in blob for marker in PARKED_MARKERS):
        score += 55
        reasons.append("parked or domain-for-sale page")
    if any(marker in blob for marker in SOFT_404_MARKERS) and _confidence_score(node) < 70:
        score += 50
        reasons.append("404/soft-404 or missing profile marker")
    if node_type == "public_deeplink" and any(marker in value for marker in ("wa.me", "t.me", "telegram", "whatsapp")):
        score += 30
        reasons.append("deeplink landing page is not registration proof")
    if _confidence_score(node) < 40:
        score += 20
        reasons.append("low confidence baseline")
    return {"node_id": _node_id(node), "label": _label(node), "type": node_type, "is_noise": score >= 50, "noise_score": min(100, score), "reasons": reasons or ["no major noise marker detected"]}


def build_noise_report(nodes: list[dict[str, Any]]) -> dict[str, Any]:
    assessments = [assess_noise(node) for node in nodes]
    return {
        "filtered_count": len([item for item in assessments if item["is_noise"]]),
        "items": sorted(assessments, key=lambda item: item["noise_score"], reverse=True)[:80],
    }


def _feature_values(node: dict[str, Any]) -> dict[str, set[str]]:
    data = _data(node)
    artifact = data.get("artifact") if isinstance(data.get("artifact"), dict) else {}
    values: dict[str, set[str]] = defaultdict(set)
    raw_fields = {
        "avatar_hash": ["avatar_hash", "email_hash_md5", "md5", "sha256", "image_hash", "favicon_hash", "payload_sha256"],
        "username": ["username", "handle", "login", "screen_name"],
        "external_link": ["external_link", "website", "url", "source_url", "profile_url"],
        "domain_email": ["email", "domain", "mx_domain"],
        "display_name": ["display_name", "name", "title"],
        "location_text": ["location", "location_text", "city", "country"],
        "analytics_favicon_cert": ["analytics_id", "gtag", "ua_id", "favicon_hash", "cert_sha256", "certificate", "serial_number"],
    }
    combined = {**artifact, **data, "label": _label(node), "value": _value(node), "source_url": _source_url(node)}
    for feature, keys in raw_fields.items():
        for key in keys:
            value = combined.get(key)
            if isinstance(value, str) and value.strip():
                values[feature].add(value.strip().lower())
            elif isinstance(value, list):
                values[feature].update(str(item).strip().lower() for item in value if str(item).strip())
    if _node_type(node) == "username":
        values["username"].add(_value(node).lower().lstrip("@"))
    if _node_type(node) == "email" and "@" in _value(node):
        local, domain = _value(node).lower().split("@", 1)
        values["username"].add(local)
        values["domain_email"].add(domain)
    if _node_type(node) == "domain":
        values["domain_email"].add(_value(node).lower())
    return values


def build_correlations(nodes: list[dict[str, Any]], existing_edges: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    existing = {(str(edge.get("source")), str(edge.get("target")), str(edge.get("type", "")).lower()) for edge in existing_edges or []}
    weights = {
        "avatar_hash": 42,
        "username": 24,
        "external_link": 25,
        "domain_email": 30,
        "display_name": 16,
        "location_text": 14,
        "analytics_favicon_cert": 46,
    }
    features = {str(_node_id(node)): _feature_values(node) for node in nodes if _node_id(node)}
    by_id = {str(_node_id(node)): node for node in nodes if _node_id(node)}
    correlations: list[dict[str, Any]] = []
    ids = list(by_id)
    for left_index, left_id in enumerate(ids):
        for right_id in ids[left_index + 1:]:
            if (left_id, right_id, "possible_same_actor") in existing or (right_id, left_id, "possible_same_actor") in existing:
                continue
            left = features[left_id]
            right = features[right_id]
            reasons: list[str] = []
            score = 0
            shared: dict[str, list[str]] = {}
            for feature, weight in weights.items():
                overlap = sorted((left.get(feature) or set()) & (right.get(feature) or set()))
                if overlap:
                    score += weight
                    shared[feature] = overlap[:5]
                    reasons.append(f"shared {feature}: {', '.join(overlap[:3])}")
            if _node_type(by_id[left_id]) == _node_type(by_id[right_id]) and _value(by_id[left_id]).lower() == _value(by_id[right_id]).lower():
                score += 20
                reasons.append("same entity value/type")
            if score >= 50:
                correlations.append({
                    "source": left_id,
                    "target": right_id,
                    "type": "possible_same_actor",
                    "confidence_level": min(89, score),
                    "confidence": "probable" if score >= 70 else "weak",
                    "reasons": reasons,
                    "shared_features": shared,
                    "legal_basis": "Weighted correlation over public-source artifacts; analyst confirmation required below 90%.",
                })
    correlations.sort(key=lambda item: item["confidence_level"], reverse=True)
    return correlations[:100]


def entity_enrichment(entity: dict[str, Any] | None, transforms: list[dict[str, Any]], coverage: dict[str, Any]) -> dict[str, Any]:
    if not entity:
        return {
            "entity_type": "none",
            "confidence_baseline": 0,
            "source_coverage_status": "no selected entity",
            "available_transforms": [],
            "recommended_transforms": [],
            "disabled_transforms": [item for item in transforms if not item.get("enabled")][:12],
        }
    entity_type = _node_type(entity)
    valid = [item for item in transforms if entity_type in (item.get("input_types") or []) or "*" in (item.get("input_types") or [])]
    available = [item for item in valid if item.get("enabled")]
    disabled = [item for item in valid if not item.get("enabled")]
    score = _confidence_score(entity)
    recommended = sorted(
        available,
        key=lambda item: (
            "profile" in " ".join(item.get("output_types") or []),
            "domain" in " ".join(item.get("output_types") or []),
            len(item.get("output_types") or []),
        ),
        reverse=True,
    )[:5]
    columns = _coverage_column_for_type(entity_type, _source(entity))
    status = []
    for column in columns:
        found = coverage["matrix"]["found"].get(column, 0)
        verified = coverage["matrix"]["verified"].get(column, 0)
        status.append(f"{column}: {verified}/{found} verified")
    return {
        "entity_id": _node_id(entity),
        "entity_type": entity_type,
        "confidence_baseline": score,
        "confidence_label": _confidence_label(entity),
        "source": _source(entity),
        "source_url": _source_url(entity),
        "timestamp": _data(entity).get("fetched_at") or entity.get("created_at"),
        "raw_evidence_ref": _data(entity).get("raw_evidence_ref") or (_data(entity).get("artifact") or {}).get("raw_evidence_ref"),
        "confidence_reason": _data(entity).get("confidence_reason") or (_data(entity).get("artifact") or {}).get("confidence_reason") or "Manual or legacy node; run an evidence-backed transform for full explanation.",
        "legal_note": _data(entity).get("legal_basis") or (_data(entity).get("artifact") or {}).get("legal_basis") or "Operator-added or legacy graph item; treat as unverified until evidence is attached.",
        "available_transforms": available,
        "recommended_transforms": recommended,
        "disabled_transforms": disabled,
        "source_coverage_status": status or ["No source coverage mapped yet"],
        "noise": assess_noise(entity),
    }


def build_lead_queue(nodes: list[dict[str, Any]], edges: list[dict[str, Any]], correlations: list[dict[str, Any]], noise: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    by_id = {_node_id(node): node for node in nodes if _node_id(node)}
    degree: Counter[str] = Counter()
    for edge in edges:
        if edge.get("source"):
            degree[str(edge.get("source"))] += 1
        if edge.get("target"):
            degree[str(edge.get("target"))] += 1
    strongest = sorted(
        [
            {"node_id": node_id, "label": _label(node), "type": _node_type(node), "score": _confidence_score(node), "degree": degree[node_id], "reason": "high confidence with multiple relationships"}
            for node_id, node in by_id.items()
            if _confidence_score(node) >= 75 or degree[node_id] >= 4
        ],
        key=lambda item: (item["score"], item["degree"]),
        reverse=True,
    )[:12]
    interesting = sorted(
        [
            {"node_id": _node_id(node), "label": _label(node), "type": _node_type(node), "score": _confidence_score(node), "reason": "candidate pivot with incomplete evidence"}
            for node in nodes
            if 35 <= _confidence_score(node) < 75 and not assess_noise(node)["is_noise"]
        ],
        key=lambda item: item["score"],
        reverse=True,
    )[:12]
    contradictions = []
    for item in noise.get("items", []):
        if item["is_noise"]:
            contradictions.append({"node_id": item["node_id"], "label": item["label"], "reason": "; ".join(item["reasons"])})
    next_actions = []
    for column in COVERAGE_COLUMNS:
        if coverage["matrix"]["found"].get(column, 0) == 0 and coverage["matrix"]["disabled"].get(column, 0) == 0:
            next_actions.append({"priority": "medium", "action": f"expand_{column.lower().replace(' ', '_')}", "reason": f"No {column} coverage has been collected."})
    return {
        "strongest_pivots": strongest,
        "unverified_interesting_pivots": interesting,
        "possible_same_actor_links": correlations[:12],
        "contradictions": contradictions[:12],
        "high_value_next_actions": next_actions[:12],
    }


def build_analyst_pipeline(
    *,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    task_records: list[dict[str, Any]],
    transforms: list[dict[str, Any]],
    selected_entity_id: str | None = None,
) -> dict[str, Any]:
    selected = next((node for node in nodes if _node_id(node) == selected_entity_id), None) if selected_entity_id else None
    coverage = build_coverage_matrix(nodes, task_records, transforms)
    noise = build_noise_report(nodes)
    correlations = build_correlations(nodes, edges)
    lead_queue = build_lead_queue(nodes, edges, correlations, noise, coverage)
    return {
        "generated_at": utc_now(),
        "selected_entity": entity_enrichment(selected, transforms, coverage),
        "coverage_matrix": coverage,
        "noise_killer": noise,
        "correlations": correlations,
        "lead_queue": lead_queue,
        "evidence_summary": {
            "count": len(evidence),
            "sources": dict(Counter(str(item.get("source") or "unknown") for item in evidence)),
            "hashes": [item.get("sha256") for item in evidence[:50]],
        },
    }


def html_packet(case: dict[str, Any], graph: dict[str, Any], pipeline: dict[str, Any], evidence: list[dict[str, Any]]) -> str:
    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    rows = "".join(
        f"<tr><td>{escape(str(node.get('type','')))}</td><td>{escape(str(node.get('label','')))}</td><td>{escape(str((_data(node)).get('confidence_score', node.get('confidence', ''))))}</td><td>{escape(str((_data(node)).get('raw_evidence_ref', '')))}</td></tr>"
        for node in nodes
    )
    evidence_rows = "".join(
        f"<tr><td>{escape(str(item.get('source','')))}</td><td>{escape(str((item.get('meta') or {}).get('source_url','')))}</td><td>{escape(str(item.get('sha256','')))}</td><td>{escape(str(item.get('created_at','')))}</td></tr>"
        for item in evidence
    )
    lead_items = "".join(f"<li>{escape(str(item))}</li>" for group in pipeline.get("lead_queue", {}).values() for item in (group if isinstance(group, list) else []))
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>NexusIntel Analyst Packet</title><style>
body{{background:#000;color:#fff;font-family:Inter,Arial,sans-serif;margin:24px}}code,td,th,pre{{font-family:'JetBrains Mono',monospace}}table{{width:100%;border-collapse:collapse;margin:12px 0}}td,th{{border:1px solid #333;padding:7px;vertical-align:top}}section{{border:1px solid #333;padding:14px;margin:12px 0;background:#050505}}h1,h2{{text-transform:uppercase}}</style></head><body>
<h1>NexusIntel Analyst Packet</h1><p>Case: {escape(str(case.get('target') or case.get('id')))} / Generated: {escape(str(pipeline.get('generated_at')))}</p>
<section><h2>Executive Summary</h2><p>Entities: {len(nodes)}. Relationships: {len(edges)}. Evidence objects: {len(evidence)}.</p></section>
<section><h2>Lead Queue</h2><ul>{lead_items}</ul></section>
<section><h2>Entities</h2><table><tr><th>Type</th><th>Label</th><th>Confidence</th><th>Evidence</th></tr>{rows}</table></section>
<section><h2>Evidence Table</h2><table><tr><th>Source</th><th>URL</th><th>SHA-256</th><th>Captured</th></tr>{evidence_rows}</table></section>
<section><h2>Pipeline JSON</h2><pre>{escape(json.dumps(pipeline, indent=2, default=str))}</pre></section>
</body></html>"""


def json_packet(case: dict[str, Any], graph: dict[str, Any], pipeline: dict[str, Any], evidence: list[dict[str, Any]]) -> str:
    return json.dumps({"case": case, "graph": graph, "analyst_pipeline": pipeline, "evidence": evidence}, indent=2, default=str)


def ioc_csv(graph: dict[str, Any]) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["type", "value", "label", "confidence", "source", "source_url", "raw_evidence_ref"])
    for node in graph.get("nodes") or []:
        data = _data(node)
        writer.writerow([_node_type(node), _value(node), _label(node), node.get("confidence") or data.get("confidence_score") or "", _source(node), _source_url(node), data.get("raw_evidence_ref") or ""])
    return output.getvalue()


def _pdf_safe(value: Any) -> str:
    return re.sub(r"[^\x20-\x7E]", "?", str(value or "")).replace("\\", "/").replace("(", "[").replace(")", "]")


def _wrap_pdf(value: Any, width: int = 88, limit: int = 8) -> list[str]:
    words = _pdf_safe(value).split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            if current:
                lines.append(current)
            current = word[:width]
        else:
            current = f"{current} {word}".strip()
        if len(lines) >= limit:
            break
    if current and len(lines) < limit:
        lines.append(current)
    return lines or ["Insufficient evidence recorded."]


def _pdf_text(x: int, y: int, text: Any, size: int = 9, font: str = "F1", color: tuple[float, float, float] = (0.07, 0.08, 0.1)) -> str:
    r, g, b = color
    return f"BT {r:.3f} {g:.3f} {b:.3f} rg /{font} {size} Tf {x} {y} Td ({_pdf_safe(text)[:145]}) Tj ET"


def _pdf_rect(x: int, y: int, w: int, h: int, color: tuple[float, float, float]) -> str:
    r, g, b = color
    return f"q {r:.3f} {g:.3f} {b:.3f} rg {x} {y} {w} {h} re f Q"


def _pdf_table_row(columns: list[Any], widths: list[int], y: int, bold: bool = False) -> list[str]:
    commands = [_pdf_rect(36, y - 5, 540, 17, (0.95, 0.96, 0.97) if bold else (1, 1, 1))]
    x = 42
    for column, width in zip(columns, widths, strict=False):
        commands.append(_pdf_text(x, y, str(column)[: max(8, width // 5)], 7, "F2" if bold else "F1"))
        x += width
    return commands


def designed_pdf_packet(case: dict[str, Any], graph: dict[str, Any], pipeline: dict[str, Any], evidence: list[dict[str, Any]]) -> bytes:
    """Generate a compact intelligence dossier without adding a PDF dependency.

    The export endpoint stays intact; this renderer only improves the PDF
    presentation. Every line is sourced from the case, graph, pipeline, and
    evidence payloads already returned by the backend.
    """

    nodes = graph.get("nodes") or []
    edges = graph.get("edges") or []
    generated = str(pipeline.get("generated_at") or utc_now())
    case_target = str(case.get("target") or case.get("id") or "Detached case")
    analyst = str(case.get("operator") or case.get("created_by") or "Operator")
    packet_hash = hashlib.sha256(json.dumps({"case": case, "graph": graph, "pipeline": pipeline, "evidence": evidence}, default=str, sort_keys=True).encode()).hexdigest()
    coverage = pipeline.get("coverage_matrix") or {}
    noise = pipeline.get("noise_killer") or {}
    leads = pipeline.get("lead_queue") or {}
    evidence_summary = pipeline.get("evidence_summary") or {}
    correlations = pipeline.get("correlations") or []

    pages: list[list[str]] = []

    def new_page(title: str) -> list[str]:
        page_no = len(pages) + 1
        commands = [
            _pdf_rect(0, 0, 612, 792, (1, 1, 1)),
            _pdf_rect(0, 748, 612, 44, (0.04, 0.04, 0.05)),
            _pdf_rect(36, 727, 540, 16, (0.74, 0.05, 0.08)),
            _pdf_text(44, 760, "NEXUSINTEL", 15, "F2", (1, 1, 1)),
            _pdf_text(446, 760, "CYBER THREAT ASSESSMENT", 8, "F2", (1, 1, 1)),
            _pdf_text(238, 731, "SECURE / CONFIDENTIAL / EVIDENCE-BACKED", 7, "F2", (1, 1, 1)),
            _pdf_text(36, 705, title.upper(), 13, "F2"),
            _pdf_rect(36, 54, 540, 1, (0.78, 0.08, 0.1)),
            _pdf_text(36, 37, f"Report hash: {packet_hash[:18]}...  Generated: {generated}", 7, "F3", (0.28, 0.3, 0.34)),
            _pdf_text(520, 37, f"Page {page_no}", 7, "F3", (0.28, 0.3, 0.34)),
        ]
        pages.append(commands)
        return commands

    def add_paragraph(commands: list[str], y: int, text: Any, width: int = 92, color: tuple[float, float, float] = (0.12, 0.13, 0.16)) -> int:
        for line in _wrap_pdf(text, width=width, limit=10):
            commands.append(_pdf_text(48, y, line, 8, "F1", color))
            y -= 12
        return y - 4

    def ensure(commands: list[str], y: int, title: str) -> tuple[list[str], int]:
        if y > 82:
            return commands, y
        return new_page(title), 690

    cover = new_page("Cyber Threat Assessment Report")
    cover.extend([
        _pdf_rect(36, 488, 540, 164, (0.04, 0.04, 0.05)),
        _pdf_text(58, 612, "CYBER THREAT ASSESSMENT REPORT", 24, "F2", (1, 1, 1)),
        _pdf_text(60, 584, f"Case Target: {case_target}", 10, "F1", (0.92, 0.92, 0.94)),
        _pdf_text(60, 563, f"Case ID: {case.get('id') or 'not available'}", 9, "F3", (0.78, 0.8, 0.84)),
        _pdf_text(60, 543, f"Analyst/Operator: {analyst}", 9, "F1", (0.92, 0.92, 0.94)),
        _pdf_text(60, 523, f"Generated: {generated}", 9, "F1", (0.92, 0.92, 0.94)),
        _pdf_text(60, 503, f"Report Hash: {packet_hash}", 7, "F3", (0.86, 0.88, 0.92)),
        _pdf_text(48, 438, "EXECUTIVE SUMMARY", 13, "F2"),
    ])
    add_paragraph(cover, 414, f"This dossier summarizes {len(nodes)} entities, {len(edges)} relationships, and {len(evidence)} evidence records currently associated with the investigation. Findings remain evidence-scoped; unsupported attribution is marked as insufficient evidence.")
    cover.extend([
        _pdf_text(48, 334, "KEY COUNTS", 11, "F2"),
        *_pdf_table_row(["Entities", "Relationships", "Evidence", "Noise removed"], [120, 130, 120, 150], 312, True),
        *_pdf_table_row([len(nodes), len(edges), len(evidence), noise.get("filtered_count", 0)], [120, 130, 120, 150], 292),
    ])

    current = new_page("Scope and Methodology")
    y = 690
    current.append(_pdf_text(48, y, "SCOPE", 11, "F2")); y -= 20
    y = add_paragraph(current, y, f"Investigation target: {case_target}. Collection uses public-source OSINT, analyst-provided evidence, configured connectors, and existing NexusIntel transform outputs. No fake or synthetic intelligence is inserted into the packet.")
    current.append(_pdf_text(48, y, "METHODOLOGY", 11, "F2")); y -= 20
    y = add_paragraph(current, y, "Confidence is derived from source reliability, directness, freshness, corroboration, contradiction penalties, and noise suppression. AI summaries, when present, are treated as analyst assistance and not as evidence.")
    current.append(_pdf_text(48, y, "COVERAGE SNAPSHOT", 11, "F2")); y -= 20
    columns = coverage.get("columns") if isinstance(coverage, dict) else []
    matrix = coverage.get("matrix") if isinstance(coverage, dict) else {}
    if columns and isinstance(matrix, dict):
        for row_name in ("attempted", "found", "verified", "noisy"):
            values = matrix.get(row_name) or {}
            current, y = ensure(current, y, "Scope and Methodology")
            current.append(_pdf_text(52, y, f"{row_name}: " + ", ".join(f"{column}={values.get(column, 0)}" for column in columns[:8]), 7, "F3"))
            y -= 12
    else:
        y = add_paragraph(current, y, "Coverage matrix is not available for this case.")

    current = new_page("Entities and Relationships")
    y = 690
    current.extend(_pdf_table_row(["Type", "Label", "Confidence", "Evidence"], [112, 210, 88, 130], y, True)); y -= 18
    if nodes:
        for node in nodes[:42]:
            current, y = ensure(current, y, "Entities and Relationships")
            data = _data(node)
            current.extend(_pdf_table_row([_node_type(node), _label(node), data.get("confidence_score", node.get("confidence", "")), data.get("raw_evidence_ref") or _source_url(node) or "insufficient evidence"], [112, 210, 88, 130], y))
            y -= 18
    else:
        y = add_paragraph(current, y, "No graph entities are available.")
    current, y = ensure(current, y - 8, "Entities and Relationships")
    current.append(_pdf_text(48, y, "RELATIONSHIPS", 11, "F2")); y -= 22
    current.extend(_pdf_table_row(["Source", "Type", "Target", "Confidence"], [145, 120, 145, 90], y, True)); y -= 18
    if edges:
        for edge in edges[:46]:
            current, y = ensure(current, y, "Entities and Relationships")
            current.extend(_pdf_table_row([edge.get("source"), edge.get("type"), edge.get("target"), edge.get("confidence_level", edge.get("confidence", ""))], [145, 120, 145, 90], y))
            y -= 18
    else:
        y = add_paragraph(current, y, "No relationships are available.")

    current = new_page("Evidence and Confidence")
    y = 690
    current.append(_pdf_text(48, y, "EVIDENCE TABLE", 11, "F2")); y -= 22
    current.extend(_pdf_table_row(["Evidence ID", "Source", "URL/Hash", "Captured"], [116, 100, 210, 110], y, True)); y -= 18
    if evidence:
        for item in evidence[:46]:
            current, y = ensure(current, y, "Evidence and Confidence")
            meta = item.get("meta") if isinstance(item.get("meta"), dict) else {}
            current.extend(_pdf_table_row([item.get("id") or item.get("evidence_id") or "evidence", item.get("source") or "unknown", meta.get("source_url") or item.get("sha256") or "not available", item.get("created_at") or item.get("fetched_at") or ""], [116, 100, 210, 110], y))
            y -= 18
    else:
        y = add_paragraph(current, y, "No evidence records are available. Report-safe findings should be treated as insufficient evidence until evidence is attached.")
    current, y = ensure(current, y - 8, "Evidence and Confidence")
    current.append(_pdf_text(48, y, "CONFIDENCE ASSESSMENT", 11, "F2")); y -= 20
    sources = evidence_summary.get("sources") if isinstance(evidence_summary, dict) else {}
    y = add_paragraph(current, y, f"Evidence sources: {sources or 'not available'}. Hashes captured: {len(evidence_summary.get('hashes') or []) if isinstance(evidence_summary, dict) else 0}. Unsupported findings should not be reported as facts.")

    current = new_page("Noise, Leads, Correlations")
    y = 690
    current.append(_pdf_text(48, y, "NOISE REMOVED", 11, "F2")); y -= 20
    noise_items = noise.get("items") if isinstance(noise, dict) else []
    if noise_items:
        for item in noise_items[:14]:
            current, y = ensure(current, y, "Noise, Leads, Correlations")
            y = add_paragraph(current, y, f"{item.get('label') or item.get('node_id')}: {', '.join(item.get('reasons') or [])}", width=96, color=(0.2, 0.22, 0.26))
    else:
        y = add_paragraph(current, y, "No suppressed noise is recorded.")
    current, y = ensure(current, y, "Noise, Leads, Correlations")
    current.append(_pdf_text(48, y, "CANDIDATE LEADS", 11, "F2")); y -= 20
    flat_leads = [str(item) for group in leads.values() for item in (group if isinstance(group, list) else [])] if isinstance(leads, dict) else []
    if flat_leads:
        for item in flat_leads[:16]:
            current, y = ensure(current, y, "Noise, Leads, Correlations")
            y = add_paragraph(current, y, item, width=96, color=(0.2, 0.22, 0.26))
    else:
        y = add_paragraph(current, y, "No candidate leads are pending.")
    current, y = ensure(current, y, "Noise, Leads, Correlations")
    current.append(_pdf_text(48, y, "CORRELATIONS", 11, "F2")); y -= 20
    if correlations:
        for item in correlations[:10]:
            current, y = ensure(current, y, "Noise, Leads, Correlations")
            y = add_paragraph(current, y, f"{item.get('source')} -> {item.get('target')} score={item.get('score')} status={item.get('relationship') or 'hypothesis'}", width=96)
    else:
        y = add_paragraph(current, y, "No reportable correlations are available.")

    current = new_page("Recommended Next Steps and Appendix")
    y = 690
    current.append(_pdf_text(48, y, "RECOMMENDED NEXT STEPS", 11, "F2")); y -= 20
    for item in [
        "Attach source URLs or raw evidence references to unsupported findings before external reporting.",
        "Resolve candidate leads through passive, legal transforms before promoting them to verified findings.",
        "Review noise bin decisions if a suppressed artifact becomes relevant to the investigative objective.",
        "Export JSON/HTML bundle for full machine-readable lineage when sharing with another analyst.",
    ]:
        y = add_paragraph(current, y, f"- {item}", width=96)
    current, y = ensure(current, y, "Recommended Next Steps and Appendix")
    current.append(_pdf_text(48, y, "APPENDIX: RAW EVIDENCE HASHES", 11, "F2")); y -= 20
    hashes = [str(item.get("sha256") or item.get("payload_sha256") or "") for item in evidence if item.get("sha256") or item.get("payload_sha256")]
    if hashes:
        for digest in hashes[:34]:
            current, y = ensure(current, y, "Recommended Next Steps and Appendix")
            current.append(_pdf_text(52, y, digest, 7, "F3"))
            y -= 11
    else:
        y = add_paragraph(current, y, "No raw evidence hashes are available.")

    content_objects = ["\n".join(commands).encode("latin-1", errors="replace") for commands in pages]
    base_objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        b"2 0 obj << /Type /Pages /Kids [" + b" ".join(f"{6 + index * 2} 0 R".encode() for index in range(len(pages))) + b"] /Count " + str(len(pages)).encode() + b" >> endobj",
        b"3 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> endobj",
        b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Courier >> endobj",
    ]
    page_objects: list[bytes] = []
    for index, stream in enumerate(content_objects):
        page_num = 6 + index * 2
        content_num = page_num + 1
        page_objects.append(f"{page_num} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R /F2 4 0 R /F3 5 0 R >> >> /Contents {content_num} 0 R >> endobj".encode())
        page_objects.append(f"{content_num} 0 obj << /Length {len(stream)} >> stream\n".encode() + stream + b"\nendstream endobj")
    objects = base_objects + page_objects
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj + b"\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(pdf)


def minimal_pdf(title: str, lines: list[str]) -> bytes:
    safe_lines = [re.sub(r"[^\x20-\x7E]", "?", line)[:110] for line in lines[:70]]
    text_commands = ["BT", "/F1 14 Tf", "50 780 Td", f"({title}) Tj", "/F1 9 Tf"]
    for line in safe_lines:
        text_commands.append("0 -14 Td")
        text_commands.append(f"({line.replace('\\\\', '/').replace('(', '[').replace(')', ']')}) Tj")
    text_commands.append("ET")
    stream = "\n".join(text_commands).encode("latin-1", errors="replace")
    objects = [
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj",
        b"4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Courier >> endobj",
        b"5 0 obj << /Length " + str(len(stream)).encode() + b" >> stream\n" + stream + b"\nendstream endobj",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf.extend(obj + b"\n")
    xref = len(pdf)
    pdf.extend(f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(pdf)
