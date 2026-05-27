
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ReportExportOptions:
    sections: list[str] = field(default_factory=list)
    include_candidates: bool = False
    include_noise_appendix: bool = True
    include_graph_snapshot: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
