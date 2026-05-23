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
