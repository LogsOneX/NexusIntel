from __future__ import annotations

import csv
import io
from typing import Any


def preview_csv(content: str, limit: int = 25) -> dict[str, Any]:
    sample = content[:2_000_000]
    reader = csv.DictReader(io.StringIO(sample))
    rows = []
    for index, row in enumerate(reader):
        if index >= limit:
            break
        rows.append(dict(row))
    return {"headers": reader.fieldnames or [], "rows": rows, "row_count_previewed": len(rows)}


def spiderfoot_mapping(headers: list[str]) -> dict[str, str]:
    lowered = {header.lower(): header for header in headers}
    return {
        "type": lowered.get("type") or lowered.get("module") or "type",
        "value": lowered.get("data") or lowered.get("value") or lowered.get("entity") or "data",
        "source": lowered.get("source") or lowered.get("module") or "source",
        "confidence": lowered.get("confidence") or lowered.get("risk") or "confidence",
    }


def preview_json(content: str, limit: int = 25) -> dict[str, Any]:
    import json
    payload = json.loads(content[:5_000_000])
    if isinstance(payload, list):
        rows = payload[:limit]
    elif isinstance(payload, dict):
        for key in ("items", "results", "data", "profiles", "entries", "iocs"):
            value = payload.get(key)
            if isinstance(value, list):
                rows = value[:limit]
                break
        else:
            rows = [payload]
    else:
        rows = [{"value": str(payload)}]
    clean_rows = [row if isinstance(row, dict) else {"value": row} for row in rows]
    headers = sorted({str(key) for row in clean_rows for key in row.keys()})
    return {"headers": headers, "rows": clean_rows, "row_count_previewed": len(clean_rows)}


def generic_ioc_mapping(headers: list[str]) -> dict[str, str]:
    lowered = {header.lower(): header for header in headers}
    return {
        "type": lowered.get("type") or lowered.get("ioc_type") or lowered.get("indicator_type") or "type",
        "value": lowered.get("value") or lowered.get("ioc") or lowered.get("indicator") or lowered.get("observable") or "value",
        "source": lowered.get("source") or lowered.get("tool") or "source",
        "confidence": lowered.get("confidence") or lowered.get("score") or "confidence",
    }


def preview_import_content(format: str, content: str, limit: int = 25) -> dict[str, Any]:
    if format.endswith("json"):
        preview = preview_json(content, limit)
        return {"preview": preview, "mapping": generic_ioc_mapping(preview["headers"]), "parser": "json"}
    preview = preview_csv(content, limit)
    mapping = spiderfoot_mapping(preview["headers"]) if format == "spiderfoot_csv" else generic_ioc_mapping(preview["headers"])
    if format == "maltego_csv":
        mapping = {**mapping, "maltego_entity": mapping.get("type", "type")}
    return {"preview": preview, "mapping": mapping, "parser": "csv"}
