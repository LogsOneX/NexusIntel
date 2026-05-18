from dataclasses import dataclass, field
from typing import Any


EntityRef = dict[str, Any]
RelationshipRef = dict[str, Any]


def entity(
    type_: str,
    value: str,
    label: str | None = None,
    confidence: int = 50,
    source: str = "system",
    properties: dict[str, Any] | None = None,
) -> EntityRef:
    return {
        "type": type_,
        "value": str(value),
        "label": label or str(value),
        "confidence": confidence,
        "source": source,
        "properties": properties or {},
    }


def relationship(
    source: EntityRef,
    target: EntityRef,
    type_: str,
    label: str | None = None,
    confidence: int = 50,
    properties: dict[str, Any] | None = None,
) -> RelationshipRef:
    return {
        "source": source,
        "target": target,
        "type": type_,
        "label": label or type_.replace("_", " ").title(),
        "confidence": confidence,
        "properties": properties or {},
    }


@dataclass
class FindingBatch:
    module: str
    summary: str
    entities: list[EntityRef] = field(default_factory=list)
    relationships: list[RelationshipRef] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "module": self.module,
            "summary": self.summary,
            "entities": self.entities,
            "relationships": self.relationships,
            "raw": self.raw,
        }
