from __future__ import annotations

from typing import Any


class ReportReadinessEngine:
    def score(self, graph: dict[str, Any], validation: dict[str, Any], noise: dict[str, Any], hypotheses: list[dict[str, Any]], evidence_records: list[dict[str, Any]]) -> dict[str, Any]:
        counts = validation.get("counts", {})
        total = max(1, len(validation.get("results", [])))
        strong = counts.get("VERIFIED", 0) + counts.get("STRONG", 0)
        weak = counts.get("WEAK", 0) + counts.get("CANDIDATE", 0) + counts.get("INSUFFICIENT_EVIDENCE", 0)
        contradicted = counts.get("CONTRADICTED", 0)
        noisy = noise.get("removed_count", 0)
        diversity = len({str(item.get("source") or "unknown") for item in evidence_records})
        score = int(max(0, min(100, (strong / total) * 55 + min(25, len(evidence_records) * 3) + min(15, diversity * 4) - weak * 5 - contradicted * 12 - min(20, noisy * 2))))
        blockers: list[str] = []
        warnings: list[str] = []
        if not evidence_records:
            blockers.append("No evidence vault records are attached to this case.")
        if contradicted:
            blockers.append("Unresolved contradictions exist.")
        if weak:
            warnings.append(f"{weak} weak/candidate/insufficient findings need review.")
        if noisy:
            warnings.append(f"{noisy} items were suppressed as noise and should be reviewed before export.")
        safe = [item for item in validation.get("results", []) if item.get("validation_label") in {"VERIFIED", "STRONG"}]
        unsafe = [item for item in validation.get("results", []) if item.get("validation_label") not in {"VERIFIED", "STRONG"}]
        recommended = []
        if blockers:
            recommended.append("Collect direct public evidence and raw hashes before final reporting.")
        if hypotheses:
            recommended.append("Resolve active hypotheses or label them as analyst-assessed hypotheses, not facts.")
        return {"score": score, "blockers": blockers, "warnings": warnings, "recommended_actions": recommended, "report_safe_findings": safe, "findings_not_safe_to_report": unsafe, "attribution_risk": "high" if any(item.get("confidence_score", 0) < 95 for item in hypotheses) else "controlled"}
