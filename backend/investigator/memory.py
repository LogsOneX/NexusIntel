from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class InvestigatorMemory:
    def __init__(self, max_items: int = 80) -> None:
        self.max_items = max_items

    def get(self, meta: dict[str, Any]) -> dict[str, Any]:
        return meta.get("ai_memory") if isinstance(meta.get("ai_memory"), dict) else {"summaries": [], "validated_findings": [], "rejected_noise": [], "active_hypotheses": [], "analyst_decisions": [], "report_ready_facts": []}

    def refresh(self, meta: dict[str, Any], validation: dict[str, Any], noise: dict[str, Any], hypotheses: list[dict[str, Any]], report: dict[str, Any]) -> dict[str, Any]:
        memory = self.get(meta)
        summary = {"created_at": now_iso(), "validation_counts": validation.get("counts", {}), "noise_removed": noise.get("removed_count", 0), "hypotheses": len(hypotheses), "report_readiness": report.get("score", 0)}
        memory["summaries"] = [summary, *memory.get("summaries", [])][: self.max_items]
        memory["validated_findings"] = [item for item in validation.get("results", []) if item.get("validation_label") in {"VERIFIED", "STRONG"}][: self.max_items]
        memory["rejected_noise"] = [item for item in noise.get("items", []) if item.get("is_noise")][: self.max_items]
        memory["active_hypotheses"] = hypotheses[: self.max_items]
        memory["report_ready_facts"] = report.get("report_safe_findings", [])[: self.max_items]
        return memory
