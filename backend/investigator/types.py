from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class HypothesisStatus(str, Enum):
    PROPOSED = "proposed"
    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INCONCLUSIVE = "inconclusive"
    REJECTED = "rejected"


@dataclass(slots=True)
class EvidenceCitation:
    evidence_id: str | None
    source: str
    source_url: str | None = None
    payload_sha256: str | None = None
    fetched_at: str | None = None
    note: str = "public-source evidence reference"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class FindingAssessment:
    finding_id: str
    subject_id: str | None
    subject_label: str
    subject_type: str
    status: str
    confidence_score: int
    confidence_reason: str
    evidence_refs: list[EvidenceCitation] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    contradictions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence_refs"] = [ref.to_dict() for ref in self.evidence_refs]
        return data


@dataclass(slots=True)
class ValidationResult:
    target_id: str | None
    label: str
    validation_label: str
    final_confidence: int
    source_reliability: int
    evidence_directness: int
    freshness: int
    corroboration: int
    contradiction_penalty: int
    noise_penalty: int
    explanation: list[str] = field(default_factory=list)
    evidence_refs: list[EvidenceCitation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence_refs"] = [ref.to_dict() for ref in self.evidence_refs]
        return data


@dataclass(slots=True)
class NoiseDecision:
    is_noise: bool
    noise_score: int
    reasons: list[str]
    recommended_action: str
    affected_node_ids: list[str] = field(default_factory=list)
    evidence_refs: list[EvidenceCitation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence_refs"] = [ref.to_dict() for ref in self.evidence_refs]
        return data


@dataclass(slots=True)
class Hypothesis:
    hypothesis_id: str
    statement: str
    status: HypothesisStatus
    supporting_evidence: list[EvidenceCitation]
    contradicting_evidence: list[EvidenceCitation]
    confidence_score: int
    confidence_reason: str
    next_tests: list[str]
    required_transforms: list[str]
    analyst_warning: str

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["status"] = self.status.value
        data["supporting_evidence"] = [ref.to_dict() for ref in self.supporting_evidence]
        data["contradicting_evidence"] = [ref.to_dict() for ref in self.contradicting_evidence]
        return data


@dataclass(slots=True)
class NextAction:
    action_id: str
    label: str
    transform_id: str | None
    target_entity_id: str | None
    why: str
    expected_outputs: list[str]
    estimated_cost: str
    required_api_key: str | None
    noise_risk: str
    safety_boundary: str
    mode: str
    should_run_now: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class InvestigationPlan:
    mode: str
    next_actions: list[NextAction]
    coverage_gaps: list[str]
    warnings: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {"mode": self.mode, "next_actions": [item.to_dict() for item in self.next_actions], "coverage_gaps": self.coverage_gaps, "warnings": self.warnings}


@dataclass(slots=True)
class ModelProfile:
    name: str
    intended_ram: str
    max_context: int
    role: str
    default_max_tokens: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LocalLLMRequest:
    prompt: str
    system_prompt: str
    profile: ModelProfile
    json_mode: bool = True
    max_tokens: int = 700
    temperature: float = 0.1


@dataclass(slots=True)
class LocalLLMResponse:
    provider: str
    mode: str
    model: str | None
    content: str
    parsed_json: dict[str, Any] | None = None
    elapsed_ms: int = 0
    fallback: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class InvestigatorQuestion:
    prompt: str
    investigation_id: str | None = None
    selected_entity_id: str | None = None
    mode: str = "balanced"


@dataclass(slots=True)
class InvestigatorAnswer:
    reply: str
    provider: str
    mode: str
    evidence_refs: list[EvidenceCitation]
    validation_summary: dict[str, Any]
    noise_summary: dict[str, Any]
    hypotheses: list[dict[str, Any]]
    next_actions: list[dict[str, Any]]
    commands: list[dict[str, Any]]
    confidence_warnings: list[str]
    report_readiness: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "reply": self.reply,
            "provider": self.provider,
            "mode": self.mode,
            "evidence_refs": [ref.to_dict() for ref in self.evidence_refs],
            "validation_summary": self.validation_summary,
            "noise_summary": self.noise_summary,
            "hypotheses": self.hypotheses,
            "next_actions": self.next_actions,
            "commands": self.commands,
            "confidence_warnings": self.confidence_warnings,
            "report_readiness": self.report_readiness,
        }
