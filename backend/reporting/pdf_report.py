
from __future__ import annotations

from typing import Any

from backend.osint.services.analyst_pipeline import designed_pdf_packet as _designed_pdf_packet


def designed_pdf_packet(case: dict[str, Any], graph: dict[str, Any], pipeline: dict[str, Any], evidence: list[dict[str, Any]]) -> bytes:
    return _designed_pdf_packet(case, graph, pipeline, evidence)
