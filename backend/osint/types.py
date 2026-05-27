from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SourceReliability(str, Enum):
    PRIMARY = "primary_public"
    OFFICIAL_API = "official_api"
    PUBLIC_WEB = "public_web"
    ANALYST_PROVIDED = "analyst_provided"
    DERIVED = "derived"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class RateLimitProfile:
    requests_per_minute: int = 30
    concurrency: int = 4
    backoff_seconds: float = 1.5


@dataclass(slots=True)
class EntityInput:
    type: str
    value: str
    label: str | None = None
    entity_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RunContext:
    investigation_id: str
    run_id: str
    api_keys: dict[str, str] = field(default_factory=dict)
    options: dict[str, Any] = field(default_factory=dict)
    operator: str = "operator"


@dataclass(slots=True)
class EvidenceRef:
    id: str | None
    source: str
    source_url: str | None
    fetched_at: str
    sha256: str | None = None
    content_type: str = "text/plain"
    note: str = "public-source read-only evidence"


@dataclass(slots=True)
class ConfidenceAssessment:
    score: int
    reason: str
    source_reliability: SourceReliability = SourceReliability.PUBLIC_WEB
    directness: str = "direct_public_observation"
    false_positive_risk: str = "medium"


@dataclass(slots=True)
class RawEvidenceObject:
    source: str
    source_url: str | None
    payload: str | dict[str, Any]
    content_type: str = "text/plain"
    headers: dict[str, Any] = field(default_factory=dict)
    fetched_at: str = field(default_factory=utc_now)
    evidence_id: str | None = None


@dataclass(slots=True)
class OSINTArtifact:
    type: str
    label: str
    value: str
    source: str
    source_url: str | None
    fetched_at: str
    confidence_score: int
    confidence_reason: str
    evidence_grade: str
    raw_evidence_ref: str | None
    relationship: str
    tags: list[str]
    data: dict[str, Any]
    legal_basis: str
    public_source_note: str = "Collected from public, passive, read-only sources or official BYOK APIs."
    artifact_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AdapterResult:
    adapter_id: str
    input: EntityInput
    artifacts: list[OSINTArtifact] = field(default_factory=list)
    raw_evidence: list[RawEvidenceObject] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    status: str = "completed"

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "input": asdict(self.input),
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "raw_evidence": [asdict(evidence) for evidence in self.raw_evidence],
            "warnings": self.warnings,
            "status": self.status,
        }


@dataclass(slots=True)
class CollectionRun:
    run_id: str
    investigation_id: str
    transform_id: str
    adapter_id: str
    status: str
    started_at: str
    finished_at: str | None = None


@dataclass(slots=True)
class TransformDefinition:
    id: str
    label: str
    description: str
    input_types: list[str]
    output_types: list[str]
    adapter_id: str
    requires_api_key: bool = False
    required_keys: list[str] = field(default_factory=list)
    passive: bool = True
    legal_note: str = "Passive public-source or official API/BYOK collection only."
    enabled: bool = True
    disabled_reason: str | None = None
    source_category: str = "public_source"
    confidence_profile: str = "evidence_scored"
    cost_profile: str = "free_or_local"
    runtime_profile: str = "interactive"
    noise_risk: str = "medium"
    evidence_behavior: str = "captures_raw_evidence_when_available"
    output_artifact_class: str = "entity_or_signal"
    recommended_next_transforms: list[str] = field(default_factory=list)
    playbook_id: str | None = None

    def to_dict(self, configured_keys: set[str] | None = None) -> dict[str, Any]:
        configured = configured_keys or set()
        missing = [key for key in self.required_keys if key not in configured]
        data = asdict(self)
        reasons: list[str] = []
        if not self.enabled:
            reasons.append(self.disabled_reason or "disabled_by_registry")
        if missing:
            reasons.append("missing_api_key:" + ",".join(missing))
        data["enabled"] = self.enabled and not missing
        data["disabled_reason"] = ";".join(reasons) if reasons else None
        return data


@dataclass(slots=True)
class TransformExecution:
    run_id: str
    transform_id: str
    status: str
    artifacts_created: int = 0
    evidence_created: int = 0
    warnings: list[str] = field(default_factory=list)


@dataclass(slots=True)
class NoiseAssessment:
    is_noise: bool
    score: int
    reason: str


class OSINTAdapter(Protocol):
    id: str
    name: str
    description: str
    input_types: list[str]
    output_types: list[str]
    requires_api_key: bool
    passive: bool
    legal_note: str
    rate_limit: RateLimitProfile

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult: ...
