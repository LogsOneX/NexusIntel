from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

FindingStatus = Literal["verified", "strong", "probable", "weak", "candidate", "noise", "contradicted", "insufficient_evidence"]

@dataclass(frozen=True, slots=True)
class EntityTypeDefinition:
    id: str
    label: str
    family: str
    description: str
    local_validation: str
    normalizer: str
    visual_icon: str
    graph_color: str
    graph_accent: str
    allowed_transforms: list[str] = field(default_factory=list)
    evidence_requirements: str = "direct_public_evidence_or_analyst_import"
    report_safety_notes: str = "Do not present unsupported claims as facts."
    candidate_noise_rules: str = "candidate_bin_until_confirmed"
    classification_default: FindingStatus = "insufficient_evidence"
    enabled: bool = True

    def to_dict(self) -> dict:
        return asdict(self)
