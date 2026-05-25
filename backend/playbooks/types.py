from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class PlaybookStep:
    id: str
    label: str
    description: str
    transform_id: str | None = None
    requires_confirmation: bool = False
    stop_condition: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PlaybookDefinition:
    id: str
    name: str
    description: str
    input_types: list[str]
    steps: list[PlaybookStep]
    required_transforms: list[str]
    optional_transforms: list[str]
    stop_conditions: list[str]
    noise_rules: list[str]
    output_report_sections: list[str]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["steps"] = [step.to_dict() for step in self.steps]
        return data


@dataclass(slots=True)
class PlaybookPlan:
    playbook_id: str
    investigation_id: str
    runnable_steps: list[dict[str, Any]] = field(default_factory=list)
    blocked_steps: list[dict[str, Any]] = field(default_factory=list)
    required_confirmation: list[dict[str, Any]] = field(default_factory=list)
    stop_conditions: list[str] = field(default_factory=list)
    output_report_sections: list[str] = field(default_factory=list)
    safety_note: str = "Passive/public-source only. Deep or broad steps require analyst confirmation."

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
