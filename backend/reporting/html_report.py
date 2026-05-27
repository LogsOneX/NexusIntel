
from __future__ import annotations

from typing import Any

from backend.osint.services.analyst_pipeline import html_packet as _html_packet


def html_packet(case: dict[str, Any], graph: dict[str, Any], pipeline: dict[str, Any], evidence: list[dict[str, Any]]) -> str:
    return _html_packet(case, graph, pipeline, evidence)
