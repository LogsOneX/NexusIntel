from __future__ import annotations

from backend.osint.types import ConfidenceAssessment, SourceReliability


def evidence_grade(score: int, reliability: SourceReliability) -> str:
    if score >= 95 and reliability in {SourceReliability.PRIMARY, SourceReliability.OFFICIAL_API, SourceReliability.PUBLIC_WEB}:
        return "A1"
    if score >= 80:
        return "A2"
    if score >= 60:
        return "B"
    if score >= 40:
        return "C"
    return "NOISE"


def assess(*, direct: bool, reliability: SourceReliability, corroborated: int = 1, fp_risk: str = "medium", reason: str = "public-source observation") -> ConfidenceAssessment:
    base = 55
    if direct:
        base += 20
    if reliability == SourceReliability.OFFICIAL_API:
        base += 20
    elif reliability == SourceReliability.PRIMARY:
        base += 18
    elif reliability == SourceReliability.PUBLIC_WEB:
        base += 12
    elif reliability == SourceReliability.ANALYST_PROVIDED:
        base += 2
    base += min(10, max(0, corroborated - 1) * 4)
    if fp_risk == "low":
        base += 6
    elif fp_risk == "high":
        base -= 18
    score = max(0, min(100, base))
    return ConfidenceAssessment(score=score, reason=reason, source_reliability=reliability, false_positive_risk=fp_risk)
