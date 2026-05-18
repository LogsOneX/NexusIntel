from collections import Counter
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models import Entity, Investigation, Relationship


def value_key(value: str) -> str:
    return " ".join(str(value).strip().lower().split())


def upsert_entity(
    session: Session,
    investigation_id: str,
    type_: str,
    value: str,
    label: str | None = None,
    confidence: int = 50,
    source: str = "system",
    properties: dict[str, Any] | None = None,
) -> Entity:
    key = value_key(value)
    entity = session.scalar(
        select(Entity).where(
            Entity.investigation_id == investigation_id,
            Entity.type == type_,
            Entity.value_key == key,
        )
    )
    merged_properties = properties or {}
    if entity:
        entity.confidence = max(entity.confidence, int(confidence))
        entity.updated_at = datetime.now(timezone.utc)
        entity.properties = {**(entity.properties or {}), **merged_properties}
        if label and len(label) > len(entity.label):
            entity.label = label[:512]
        if source and entity.source == "system":
            entity.source = source
        session.flush()
        return entity

    entity = Entity(
        investigation_id=investigation_id,
        type=type_,
        value=str(value),
        value_key=key,
        label=(label or str(value))[:512],
        confidence=max(0, min(100, int(confidence))),
        source=source,
        properties=merged_properties,
    )
    session.add(entity)
    session.flush()
    return entity


def upsert_relationship(
    session: Session,
    investigation_id: str,
    source: Entity,
    target: Entity,
    type_: str,
    label: str | None = None,
    confidence: int = 50,
    properties: dict[str, Any] | None = None,
) -> Relationship:
    relationship = session.scalar(
        select(Relationship).where(
            Relationship.investigation_id == investigation_id,
            Relationship.source_entity_id == source.id,
            Relationship.target_entity_id == target.id,
            Relationship.type == type_,
        )
    )
    if relationship:
        relationship.confidence = max(relationship.confidence, int(confidence))
        relationship.properties = {**(relationship.properties or {}), **(properties or {})}
        session.flush()
        return relationship

    relationship = Relationship(
        investigation_id=investigation_id,
        source_entity_id=source.id,
        target_entity_id=target.id,
        type=type_,
        label=label or type_.replace("_", " ").title(),
        confidence=max(0, min(100, int(confidence))),
        properties=properties or {},
    )
    session.add(relationship)
    session.flush()
    return relationship


def persist_batch(session: Session, investigation_id: str, batch: dict[str, Any]) -> dict[str, int]:
    refs: dict[tuple[str, str], Entity] = {}
    created_entities = 0
    created_edges = 0

    for item in batch.get("entities", []):
        before = session.scalar(
            select(func.count(Entity.id)).where(
                Entity.investigation_id == investigation_id,
                Entity.type == item["type"],
                Entity.value_key == value_key(item["value"]),
            )
        )
        entity = upsert_entity(
            session,
            investigation_id,
            item["type"],
            item["value"],
            item.get("label"),
            item.get("confidence", 50),
            item.get("source", batch.get("module", "system")),
            item.get("properties", {}),
        )
        refs[(entity.type, entity.value_key)] = entity
        if before == 0:
            created_entities += 1

    for edge in batch.get("relationships", []):
        source_ref = edge["source"]
        target_ref = edge["target"]
        source = refs.get((source_ref["type"], value_key(source_ref["value"]))) or upsert_entity(
            session,
            investigation_id,
            source_ref["type"],
            source_ref["value"],
            source_ref.get("label"),
            source_ref.get("confidence", 50),
            source_ref.get("source", batch.get("module", "system")),
            source_ref.get("properties", {}),
        )
        target = refs.get((target_ref["type"], value_key(target_ref["value"]))) or upsert_entity(
            session,
            investigation_id,
            target_ref["type"],
            target_ref["value"],
            target_ref.get("label"),
            target_ref.get("confidence", 50),
            target_ref.get("source", batch.get("module", "system")),
            target_ref.get("properties", {}),
        )
        before = session.scalar(
            select(func.count(Relationship.id)).where(
                Relationship.investigation_id == investigation_id,
                Relationship.source_entity_id == source.id,
                Relationship.target_entity_id == target.id,
                Relationship.type == edge["type"],
            )
        )
        upsert_relationship(
            session,
            investigation_id,
            source,
            target,
            edge["type"],
            edge.get("label"),
            edge.get("confidence", 50),
            edge.get("properties", {}),
        )
        if before == 0:
            created_edges += 1

    return {"entities": created_entities, "relationships": created_edges}


def graph_payload(session: Session, investigation_id: str) -> dict[str, Any]:
    entities = session.scalars(select(Entity).where(Entity.investigation_id == investigation_id)).all()
    relationships = session.scalars(select(Relationship).where(Relationship.investigation_id == investigation_id)).all()
    type_counts = Counter(entity.type for entity in entities)
    return {
        "nodes": [
            {
                "id": entity.id,
                "type": entity.type,
                "value": entity.value,
                "label": entity.label,
                "confidence": entity.confidence,
                "source": entity.source,
                "properties": entity.properties or {},
            }
            for entity in entities
        ],
        "edges": [
            {
                "id": relationship.id,
                "source": relationship.source_entity_id,
                "target": relationship.target_entity_id,
                "type": relationship.type,
                "label": relationship.label,
                "confidence": relationship.confidence,
                "properties": relationship.properties or {},
            }
            for relationship in relationships
        ],
        "summary": {
            "nodes": len(entities),
            "edges": len(relationships),
            "types": dict(type_counts),
        },
    }


def delete_entity(session: Session, investigation_id: str, entity_id: str) -> bool:
    entity = session.get(Entity, entity_id)
    if not entity or entity.investigation_id != investigation_id:
        return False
    session.execute(
        delete(Relationship).where(
            Relationship.investigation_id == investigation_id,
            or_(Relationship.source_entity_id == entity_id, Relationship.target_entity_id == entity_id),
        )
    )
    session.delete(entity)
    return True


def refresh_summary(session: Session, investigation: Investigation) -> None:
    graph = graph_payload(session, investigation.id)
    investigation.summary = graph["summary"]
