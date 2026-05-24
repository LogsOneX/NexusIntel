from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
import ipaddress
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Literal

import redis.asyncio as aioredis
import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

from tasks import run_crypto_wallet_task, run_domain_task, run_email_google_task, run_entity_resolution_task, run_full_identity_pipeline_task, run_google_footprint_task, run_nexusrecon_task, run_phone_task, run_serverless_invoker_task
from backend.modules.case_hygiene import build_case_hygiene_report
from backend.modules.graph_intel import build_graph_intelligence
from backend.modules.collaboration_bus import CollaborationBus
from backend.modules.provenance_store import ProvenanceStore
from backend.modules.proxy_rotator import ProxyRotator
from backend.osint.importers.csv_importers import preview_csv, spiderfoot_mapping
from backend.osint.registry import registry
from backend.osint.types import EntityInput, RawEvidenceObject, RunContext
from backend.osint.services.analyst_pipeline import build_analyst_pipeline, build_correlations, html_packet, ioc_csv, json_packet, minimal_pdf
from backend.artifact_classifier import append_artifact_to_meta, artifact_record, classify_artifact, dedupe_records, route_artifact


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://nexus:nexus@postgres:5432/nexusintel",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")]
AUTH_USER = os.getenv("NEXUS_ADMIN_USER", "admin")
AUTH_PASSWORD = os.getenv("NEXUS_ADMIN_PASSWORD", "nexusintel")
AUTH_SECRET = os.getenv("NEXUS_AUTH_SECRET", "change-this-local-secret")


engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()


class Investigation(Base):
    __tablename__ = "investigations"

    id = Column(String(36), primary_key=True)
    target = Column(String(512), nullable=False, index=True)
    target_type = Column(String(64), nullable=False, default="unknown")
    status = Column(String(32), nullable=False, default="ready")
    mode = Column(String(32), nullable=False, default="passive")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    meta = Column(JSONB, nullable=False, default=dict)

    entities = relationship("Entity", cascade="all, delete-orphan")
    relationships = relationship("Relationship", cascade="all, delete-orphan")


class Entity(Base):
    __tablename__ = "entities"
    __table_args__ = (UniqueConstraint("investigation_id", "fingerprint", name="uq_entity_fingerprint"),)

    id = Column(String(36), primary_key=True)
    investigation_id = Column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Column(String(64), nullable=False, index=True)
    label = Column(String(512), nullable=False)
    value = Column(String(2048), nullable=False)
    source = Column(String(128), nullable=False, default="manual")
    confidence = Column(String(32), nullable=False, default="medium")
    fingerprint = Column(String(768), nullable=False)
    data = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (UniqueConstraint("investigation_id", "source_id", "target_id", "type", name="uq_relationship"),)

    id = Column(String(36), primary_key=True)
    investigation_id = Column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    source_id = Column(String(36), nullable=False, index=True)
    target_id = Column(String(36), nullable=False, index=True)
    type = Column(String(64), nullable=False)
    source = Column(String(128), nullable=False, default="system")
    confidence = Column(String(32), nullable=False, default="medium")
    data = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class TaskRecord(Base):
    __tablename__ = "task_records"

    id = Column(String(36), primary_key=True)
    investigation_id = Column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    task_name = Column(String(128), nullable=False)
    status = Column(String(32), nullable=False, default="queued")
    target = Column(String(2048), nullable=False)
    celery_id = Column(String(128), nullable=True)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)
    result = Column(JSONB, nullable=False, default=dict)


class Event(Base):
    __tablename__ = "events"

    id = Column(String(36), primary_key=True)
    investigation_id = Column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id = Column(String(36), nullable=True, index=True)
    level = Column(String(32), nullable=False, default="info")
    message = Column(Text, nullable=False)
    payload = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class SettingRecord(Base):
    __tablename__ = "settings"

    key = Column(String(96), primary_key=True)
    value = Column(JSONB, nullable=False, default=dict)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class DataProvenance(Base):
    __tablename__ = "data_provenance"

    id = Column(String(36), primary_key=True)
    investigation_id = Column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    entity_id = Column(String(36), nullable=True, index=True)
    source = Column(String(256), nullable=False)
    uri = Column(String(2048), nullable=False)
    sha256 = Column(String(64), nullable=False, index=True)
    content_type = Column(String(128), nullable=False, default="application/octet-stream")
    size_bytes = Column(String(32), nullable=False, default="0")
    meta = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(128), nullable=False, default="anonymous")
    action = Column(String(128), nullable=False)
    target_entity = Column(String(256), nullable=True)
    ip_address = Column(String(128), nullable=True)
    method = Column(String(16), nullable=False)
    path = Column(String(2048), nullable=False)
    status_code = Column(String(16), nullable=False, default="0")
    meta = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class Watchlist(Base):
    __tablename__ = "watchlists"

    id = Column(String(36), primary_key=True)
    investigation_id = Column(String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True)
    target = Column(String(512), nullable=False)
    target_type = Column(String(64), nullable=False)
    enabled = Column(String(8), nullable=False, default="true")
    interval_hours = Column(String(8), nullable=False, default="12")
    last_signature = Column(String(128), nullable=True)
    last_delta = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class InvestigationCreate(BaseModel):
    target: str = Field(..., min_length=2, max_length=512)
    target_type: str | None = Field(default=None, max_length=64)
    mode: Literal["passive", "standard", "aggressive"] = "standard"


class TransformRequest(BaseModel):
    investigation_id: str
    node_id: str
    transform: str = Field(..., min_length=2, max_length=128)
    mode: Literal["passive", "standard", "aggressive"] = "standard"


class TransformRunRequest(BaseModel):
    investigation_id: str
    transform_id: str = Field(..., min_length=2, max_length=128)
    node_id: str | None = None
    input: dict[str, Any] | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class ImportPreviewRequest(BaseModel):
    format: Literal["spiderfoot_csv", "maltego_csv", "generic_ioc_csv"] = "spiderfoot_csv"
    content: str = Field(..., min_length=1, max_length=5_000_000)


class ManualEntityRequest(BaseModel):
    investigation_id: str
    type: str = Field(..., min_length=2, max_length=64)
    label: str = Field(..., min_length=1, max_length=512)
    value: str = Field(..., min_length=1, max_length=2048)
    source_id: str | None = None
    relationship_type: str = "manual_link"
    data: dict[str, Any] = Field(default_factory=dict)


class MarkNoiseRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=512)


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    password: str = Field(..., min_length=1, max_length=256)


class CaseUpdate(BaseModel):
    case_name: str | None = Field(default=None, max_length=256)
    assigned_operator: str | None = Field(default=None, max_length=128)
    notes: str | None = Field(default=None, max_length=20000)


class SettingsUpdate(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)


class OracleChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1, max_length=8000)
    investigation_id: str | None = None
    graph_state: dict[str, Any] = Field(default_factory=dict)
    node: dict[str, Any] | None = None


class OracleBriefingRequest(BaseModel):
    investigation_id: str | None = None
    graph_state: dict[str, Any] = Field(default_factory=dict)


class ApiResponse(BaseModel):
    ok: bool
    data: dict[str, Any] = Field(default_factory=dict)


class ProvenanceCreate(BaseModel):
    investigation_id: str
    entity_id: str | None = None
    source: str = Field(..., min_length=1, max_length=256)
    payload: dict[str, Any] | str


class WatchlistCreate(BaseModel):
    investigation_id: str
    target: str = Field(..., min_length=1, max_length=512)
    target_type: str | None = None
    enabled: bool = True
    interval_hours: int = Field(default=12, ge=1, le=720)


class CollaborationPatch(BaseModel):
    workspace_id: str
    patch: dict[str, Any] = Field(default_factory=dict)


class PresenceUpdate(BaseModel):
    workspace_id: str
    state: dict[str, Any] = Field(default_factory=dict)


class EntityResolutionRequest(BaseModel):
    left: dict[str, Any]
    right: dict[str, Any]


class CryptoLookupRequest(BaseModel):
    investigation_id: str
    address: str = Field(..., min_length=16, max_length=128)
    parent_node_id: str | None = None


class ServerlessInvokeRequest(BaseModel):
    investigation_id: str
    payload: dict[str, Any] = Field(default_factory=dict)


class ProxySeedRequest(BaseModel):
    proxies: list[str] = Field(default_factory=list)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def confidence_level(confidence: str | None, data: dict[str, Any] | None = None) -> int:
    if data and isinstance(data.get("confidence_level"), (int, float)):
        return max(0, min(100, int(data["confidence_level"])))
    raw = str(confidence or "medium").lower()
    if raw in {"confirmed", "exact", "high", "success"}:
        return 90
    if raw in {"medium", "observed", "probable"}:
        return 60
    if raw in {"low", "candidate", "weak"}:
        return 30
    return 50


def encode_token(username: str) -> str:
    payload = {"sub": username, "iat": int(time.time())}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(AUTH_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def verify_token(token: str | None) -> str:
    if not token or "." not in token:
        raise HTTPException(status_code=401, detail="Missing authentication token")
    body, signature = token.rsplit(".", 1)
    expected = hmac.new(AUTH_SECRET.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    try:
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Malformed authentication token") from exc
    return str(payload.get("sub") or "operator")


def current_operator(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return verify_token(authorization.split(" ", 1)[1].strip())


def classify_target(value: str) -> str:
    target = value.strip()
    if "@" in target and "." in target.split("@")[-1]:
        return "email"
    if target.replace("+", "").replace("-", "").replace(" ", "").isdigit() and len(target) >= 7:
        return "phone"
    try:
        ipaddress.ip_address(target)
        return "ip"
    except ValueError:
        pass
    if "." in target and " " not in target:
        return "domain"
    return "username"


def fingerprint(kind: str, value: str) -> str:
    return f"{kind}:{value.strip().lower()}"[:768]


def serialize_entity(entity: Entity) -> dict[str, Any]:
    return {
        "id": entity.id,
        "type": entity.type,
        "label": entity.label,
        "value": entity.value,
        "source": entity.source,
        "confidence": entity.confidence,
        "data": entity.data or {},
        "created_at": entity.created_at.isoformat() + "Z",
    }


def serialize_relationship(edge: Relationship) -> dict[str, Any]:
    return {
        "id": edge.id,
        "source": edge.source_id,
        "target": edge.target_id,
        "type": edge.type,
        "confidence": edge.confidence,
        "confidence_level": confidence_level(edge.confidence, edge.data or {}),
        "data": edge.data or {},
        "created_at": edge.created_at.isoformat() + "Z",
    }


def upsert_entity(
    db: Session,
    investigation_id: str,
    *,
    type_: str,
    label: str,
    value: str,
    source: str,
    confidence: str = "medium",
    data: dict[str, Any] | None = None,
) -> Entity:
    fp = fingerprint(type_, value)
    existing = db.execute(
        select(Entity).where(Entity.investigation_id == investigation_id, Entity.fingerprint == fp)
    ).scalar_one_or_none()
    if existing:
        merged = {**(existing.data or {}), **(data or {})}
        existing.label = label or existing.label
        existing.source = source or existing.source
        existing.confidence = confidence or existing.confidence
        existing.data = merged
        return existing

    entity = Entity(
        id=str(uuid.uuid4()),
        investigation_id=investigation_id,
        type=type_,
        label=label,
        value=value,
        source=source,
        confidence=confidence,
        fingerprint=fp,
        data=data or {},
    )
    db.add(entity)
    return entity


def upsert_relationship(
    db: Session,
    investigation_id: str,
    *,
    source_id: str,
    target_id: str,
    type_: str,
    source: str,
    confidence: str = "medium",
    data: dict[str, Any] | None = None,
) -> Relationship:
    relationship_data = {**(data or {}), "confidence_level": confidence_level(confidence, data or {})}
    existing = db.execute(
        select(Relationship).where(
            Relationship.investigation_id == investigation_id,
            Relationship.source_id == source_id,
            Relationship.target_id == target_id,
            Relationship.type == type_,
        )
    ).scalar_one_or_none()
    if existing:
        existing.confidence = confidence or existing.confidence
        existing.data = {**(existing.data or {}), **relationship_data}
        return existing

    edge = Relationship(
        id=str(uuid.uuid4()),
        investigation_id=investigation_id,
        source_id=source_id,
        target_id=target_id,
        type=type_,
        source=source,
        confidence=confidence,
        data=relationship_data,
    )
    db.add(edge)
    return edge


def artifact_like_from_entity(entity: Entity) -> dict[str, Any]:
    data = entity.data if isinstance(entity.data, dict) else {}
    artifact = data.get("artifact") if isinstance(data.get("artifact"), dict) else {}
    return {
        **artifact,
        "type": artifact.get("type") or entity.type,
        "label": artifact.get("label") or entity.label,
        "value": artifact.get("value") or entity.value,
        "source": artifact.get("source") or entity.source,
        "confidence": artifact.get("confidence") or entity.confidence,
        "relationship": artifact.get("relationship") or data.get("relationship"),
        "data": {**data, **(artifact.get("data") if isinstance(artifact.get("data"), dict) else {})},
    }


def record_from_entity(entity: Entity, classification: str) -> dict[str, Any]:
    record = artifact_record(artifact_like_from_entity(entity), classification, default_source=entity.source)
    record["entity_id"] = entity.id
    record["created_at"] = entity.created_at.isoformat() + "Z"
    return record


def graph_payload(db: Session, investigation_id: str) -> dict[str, Any]:
    investigation = db.get(Investigation, investigation_id)
    meta = investigation.meta if investigation and isinstance(investigation.meta, dict) else {}
    entities = db.execute(select(Entity).where(Entity.investigation_id == investigation_id)).scalars().all()
    relationships = db.execute(select(Relationship).where(Relationship.investigation_id == investigation_id)).scalars().all()
    nodes: list[dict[str, Any]] = []
    legacy_leads: list[dict[str, Any]] = []
    legacy_noise: list[dict[str, Any]] = []
    legacy_compliance: list[dict[str, Any]] = []
    hidden_ids: set[str] = set()
    for entity in entities:
        entity_data = entity.data if isinstance(entity.data, dict) else {}
        visibility = str(entity_data.get("graph_visibility") or "main_graph")
        route = route_artifact(artifact_like_from_entity(entity))
        if visibility in {"candidate_bin", "noise_bin", "compliance_log", "evidence_only", "signal_badge"} or not route.create_entity:
            hidden_ids.add(entity.id)
            record = record_from_entity(entity, route.artifact_class)
            if visibility == "candidate_bin" or route.artifact_class == "CANDIDATE":
                legacy_leads.append(record)
            elif visibility == "noise_bin" or route.artifact_class == "NOISE":
                legacy_noise.append(record)
            elif visibility == "compliance_log" or route.artifact_class == "COMPLIANCE":
                legacy_compliance.append(record)
            continue
        nodes.append(serialize_entity(entity))

    edges = [
        serialize_relationship(edge)
        for edge in relationships
        if edge.source_id not in hidden_ids and edge.target_id not in hidden_ids
    ]

    def meta_list(name: str) -> list[dict[str, Any]]:
        value = meta.get(name)
        return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []

    leads = dedupe_records(meta_list("leads"), legacy_leads)
    noise = dedupe_records(meta_list("noise"), legacy_noise)
    compliance = dedupe_records(meta_list("compliance"), legacy_compliance)
    return {
        "nodes": nodes,
        "edges": edges,
        "leads": leads,
        "noise": noise,
        "compliance": compliance,
        "metadata": {
            "created_entity_ids": [node["id"] for node in nodes],
            "candidate_count": len(leads),
            "noise_count": len(noise),
            "compliance_count": len(compliance),
        },
    }


def meta_records(investigation: Investigation, bucket: str) -> list[dict[str, Any]]:
    meta = investigation.meta if isinstance(investigation.meta, dict) else {}
    records = meta.get(bucket)
    return [item for item in records if isinstance(item, dict)] if isinstance(records, list) else []


def meta_record_id(record: dict[str, Any]) -> str:
    from backend.artifact_classifier import artifact_record_key
    return str(record.get("id") or artifact_record_key(record))


def pop_meta_record(investigation: Investigation, bucket: str, record_id: str) -> dict[str, Any] | None:
    meta = dict(investigation.meta or {})
    items = meta_records(investigation, bucket)
    remaining: list[dict[str, Any]] = []
    found: dict[str, Any] | None = None
    for item in items:
        item = {**item, "id": meta_record_id(item)}
        if item["id"] == record_id and found is None:
            found = item
        else:
            remaining.append(item)
    if found is not None:
        meta[bucket] = remaining
        counts = dict(meta.get("artifact_counts") or {})
        counts["candidate_count"] = len(meta.get("leads") or [])
        counts["noise_count"] = len(meta.get("noise") or [])
        counts["compliance_count"] = len(meta.get("compliance") or [])
        meta["artifact_counts"] = counts
        investigation.meta = meta
        investigation.updated_at = datetime.utcnow()
    return found


def find_meta_record(investigation: Investigation, bucket: str, record_id: str) -> dict[str, Any] | None:
    for item in meta_records(investigation, bucket):
        item = {**item, "id": meta_record_id(item)}
        if item["id"] == record_id:
            return item
    return None


def entity_from_artifact_record(db: Session, investigation_id: str, record: dict[str, Any], *, promoted: bool = False) -> Entity:
    record_type = str(record.get("type") or "profile")
    label = str(record.get("label") or record.get("value") or record_type)
    value = str(record.get("value") or label)
    source = str(record.get("source") or "analyst_promotion")
    confidence = str(record.get("confidence") or "weak")
    data = dict(record.get("data") or {})
    data.update(
        {
            "artifact_class": "ENTITY",
            "graph_visibility": "main_graph",
            "promotion_status": "promoted" if promoted else "restored",
            "promoted_from": record.get("id"),
            "source_url": record.get("source_url") or data.get("source_url"),
            "raw_evidence_ref": record.get("raw_evidence_ref") or data.get("raw_evidence_ref"),
            "confidence_score": record.get("confidence_score") or data.get("confidence_score"),
            "confidence_reason": record.get("confidence_reason") or data.get("confidence_reason"),
            "legal_basis": record.get("legal_basis") or data.get("legal_basis"),
        }
    )
    return upsert_entity(db, investigation_id, type_=record_type, label=label, value=value, source=source, confidence=confidence, data=data)

def create_task_record(db: Session, investigation_id: str, task_name: str, target: str) -> TaskRecord:
    record = TaskRecord(
        id=str(uuid.uuid4()),
        investigation_id=investigation_id,
        task_name=task_name,
        status="queued",
        target=target,
        result={},
    )
    db.add(record)
    db.flush()
    return record


API_KEY_ALIASES = {
    "GITHUB_TOKEN": ("github", "github_token"),
    "HIBP_API_KEY": ("hibp", "haveibeenpwned"),
    "URLSCAN_API_KEY": ("urlscan",),
    "GOOGLE_MAPS_API_KEY": ("google_maps", "google_places"),
    "SHODAN_API_KEY": ("shodan",),
    "CENSYS_API_KEY": ("censys",),
    "VIRUSTOTAL_API_KEY": ("virustotal", "vt"),
    "TWILIO_LOOKUP_API_KEY": ("twilio",),
    "NUMVERIFY_API_KEY": ("numverify",),
}


def osint_api_keys(db: Session) -> dict[str, str]:
    settings = get_settings(db)
    configured = settings.get("api_keys") or {}
    keys: dict[str, str] = {}
    for canonical, aliases in API_KEY_ALIASES.items():
        env_value = os.getenv(canonical, "")
        value = env_value or ""
        for alias in aliases:
            value = value or str(configured.get(alias) or "")
        if value:
            keys[canonical] = value
    return keys


def configured_osint_key_names(db: Session) -> set[str]:
    return set(osint_api_keys(db).keys())


def confidence_label_from_score(score: int) -> str:
    if score >= 95:
        return "confirmed"
    if score >= 80:
        return "high"
    if score >= 60:
        return "probable"
    if score >= 40:
        return "weak"
    return "noise"


def serialize_provenance_record(record: DataProvenance, include_payload: bool = False) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": record.id,
        "investigation_id": record.investigation_id,
        "entity_id": record.entity_id,
        "source": record.source,
        "uri": record.uri,
        "sha256": record.sha256,
        "content_type": record.content_type,
        "size_bytes": int(record.size_bytes or 0),
        "meta": record.meta or {},
        "created_at": record.created_at.isoformat() + "Z",
    }
    if include_payload:
        path = Path(record.uri)
        if path.exists() and path.is_file():
            raw = path.read_bytes()
            data["payload_preview"] = raw[:80_000].decode("utf-8", errors="replace")
            data["payload_truncated"] = len(raw) > 80_000
        else:
            data["payload_preview"] = None
            data["payload_truncated"] = False
    return data


def store_raw_evidence(db: Session, investigation_id: str, raw: RawEvidenceObject, entity_id: str | None = None) -> DataProvenance:
    stored = ProvenanceStore().put(investigation_id=investigation_id, source=raw.source, content=raw.payload)
    existing = db.execute(
        select(DataProvenance).where(
            DataProvenance.investigation_id == investigation_id,
            DataProvenance.sha256 == stored["sha256"],
            DataProvenance.source == raw.source,
        )
    ).scalar_one_or_none()
    if existing:
        if entity_id and not existing.entity_id:
            existing.entity_id = entity_id
        return existing
    record = DataProvenance(
        id=str(uuid.uuid4()),
        investigation_id=investigation_id,
        entity_id=entity_id,
        source=raw.source,
        uri=stored["uri"],
        sha256=stored["sha256"],
        content_type=raw.content_type or stored["content_type"],
        size_bytes=str(stored["size"]),
        meta={
            "storage": stored["storage"],
            "source_url": raw.source_url,
            "fetched_at": raw.fetched_at,
            "headers": raw.headers,
            "public_source_note": "Raw payload was collected from a public read-only source or official BYOK API.",
        },
    )
    db.add(record)
    db.flush()
    raw.evidence_id = record.id
    return record



def store_non_entity_artifact(
    db: Session,
    investigation_id: str,
    *,
    bucket: str,
    artifact: dict[str, Any],
    classification: str,
    default_source: str,
    parent_id: str | None = None,
) -> dict[str, Any]:
    record = artifact_record(artifact, classification, default_source=default_source, parent_id=parent_id)
    investigation = db.get(Investigation, investigation_id)
    if investigation:
        investigation.meta = append_artifact_to_meta(investigation.meta or {}, bucket, record)
        investigation.updated_at = datetime.utcnow()
    if bucket == "compliance":
        db.add(
            Event(
                id=str(uuid.uuid4()),
                investigation_id=investigation_id,
                task_id=None,
                level="info",
                message=f"Compliance artifact captured: {record.get('label') or record.get('type')}",
                payload=record,
            )
        )
    return record


def attach_signal_to_parent(parent: Entity, artifact: dict[str, Any], classification: str, *, default_source: str) -> None:
    record = artifact_record(artifact, classification, default_source=default_source, parent_id=parent.id)
    data = dict(parent.data or {})
    signals = [item for item in (data.get("signals") or []) if isinstance(item, dict)]
    ids = {str(item.get("id")) for item in signals if item.get("id")}
    if str(record.get("id")) not in ids:
        signals.append(record)
    data["signals"] = signals[-100:]
    data["signal_count"] = len(data["signals"])
    parent.data = data

def persist_adapter_result(db: Session, investigation_id: str, parent: Entity | None, result) -> dict[str, Any]:
    evidence_by_key: dict[tuple[str, str | None], DataProvenance] = {}
    evidence_records: list[DataProvenance] = []
    for raw in result.raw_evidence:
        record = store_raw_evidence(db, investigation_id, raw)
        evidence_records.append(record)
        evidence_by_key[(raw.source, raw.source_url)] = record
        evidence_by_key.setdefault((raw.source, None), record)

    created_nodes: list[dict[str, Any]] = []
    created_edges: list[dict[str, Any]] = []
    candidate_count = 0
    noise_count = 0
    compliance_count = 0
    for artifact in result.artifacts:
        evidence = None
        if artifact.raw_evidence_ref:
            evidence = db.get(DataProvenance, artifact.raw_evidence_ref)
        if not evidence:
            evidence = evidence_by_key.get((artifact.source, artifact.source_url)) or evidence_by_key.get((artifact.source, None))
        if evidence:
            artifact.raw_evidence_ref = evidence.id
        artifact_dict = artifact.to_dict()
        artifact_dict.setdefault("public_source_note", artifact.public_source_note)
        route = route_artifact(artifact_dict)
        classification = route.artifact_class
        if route.attach_to_parent and parent:
            attach_signal_to_parent(parent, artifact_dict, classification, default_source=artifact.source)
            continue
        if route.meta_bucket:
            store_non_entity_artifact(
                db,
                investigation_id,
                bucket=route.meta_bucket,
                artifact=artifact_dict,
                classification=classification,
                default_source=artifact.source,
                parent_id=parent.id if parent else None,
            )
            if classification == "COMPLIANCE":
                compliance_count += 1
            elif classification == "CANDIDATE":
                candidate_count += 1
            elif classification == "NOISE":
                noise_count += 1
            continue

        entity = upsert_entity(
            db,
            investigation_id,
            type_=artifact.type,
            label=artifact.label,
            value=artifact.value,
            source=artifact.source,
            confidence=confidence_label_from_score(artifact.confidence_score),
            data={
                **artifact.data,
                "artifact": {**artifact_dict, "classification": classification, "artifact_class": classification, "graph_visibility": route.graph_visibility},
                "artifact_class": classification,
                "graph_visibility": route.graph_visibility,
                "artifact_id": artifact.artifact_id,
                "source": artifact.source,
                "source_url": artifact.source_url,
                "fetched_at": artifact.fetched_at,
                "confidence_score": artifact.confidence_score,
                "confidence_reason": artifact.confidence_reason,
                "evidence_grade": artifact.evidence_grade,
                "raw_evidence_ref": artifact.raw_evidence_ref,
                "legal_basis": artifact.legal_basis,
                "public_source_note": artifact.public_source_note,
            },
        )
        db.flush()
        if evidence and not evidence.entity_id:
            evidence.entity_id = entity.id
        created_nodes.append(serialize_entity(entity))
        if parent and parent.id != entity.id:
            relationship = upsert_relationship(
                db,
                investigation_id,
                source_id=parent.id,
                target_id=entity.id,
                type_=artifact.relationship or "OSINT_OBSERVED",
                source=artifact.source,
                confidence=confidence_label_from_score(artifact.confidence_score),
                data={
                    "confidence_level": artifact.confidence_score,
                    "confidence_reason": artifact.confidence_reason,
                    "evidence_grade": artifact.evidence_grade,
                    "raw_evidence_ref": artifact.raw_evidence_ref,
                    "source_url": artifact.source_url,
                    "legal_basis": artifact.legal_basis,
                    "public_source_note": artifact.public_source_note,
                },
            )
            created_edges.append(serialize_relationship(relationship))
    return {
        "nodes": created_nodes,
        "edges": created_edges,
        "evidence": [serialize_provenance_record(record) for record in evidence_records],
        "warnings": list(result.warnings),
        "created_entity_ids": [node["id"] for node in created_nodes],
        "candidate_count": candidate_count,
        "noise_count": noise_count,
        "compliance_count": compliance_count,
    }


def serialize_task_record_compact(task: TaskRecord) -> dict[str, Any]:
    return {
        "id": task.id,
        "investigation_id": task.investigation_id,
        "task_name": task.task_name,
        "status": task.status,
        "target": task.target,
        "started_at": task.started_at.isoformat() + "Z" if task.started_at else None,
        "finished_at": task.finished_at.isoformat() + "Z" if task.finished_at else None,
        "error": task.error,
        "result": task.result or {},
    }


def analyst_pipeline_payload(db: Session, investigation_id: str, selected_entity_id: str | None = None) -> dict[str, Any]:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    graph = graph_payload(db, investigation_id)
    evidence_rows = db.execute(select(DataProvenance).where(DataProvenance.investigation_id == investigation_id).order_by(DataProvenance.created_at.desc())).scalars().all()
    task_rows = db.execute(select(TaskRecord).where(TaskRecord.investigation_id == investigation_id).order_by(TaskRecord.started_at.desc().nullslast(), TaskRecord.id.desc())).scalars().all()
    transforms = registry.list_transforms(configured_osint_key_names(db))
    evidence = [serialize_provenance_record(row) for row in evidence_rows]
    pipeline = build_analyst_pipeline(
        nodes=graph["nodes"],
        edges=graph["edges"],
        evidence=evidence,
        task_records=[serialize_task_record_compact(row) for row in task_rows],
        transforms=transforms,
        selected_entity_id=selected_entity_id,
    )
    return {"case": serialize_case(investigation), "graph": graph, "evidence": evidence, "task_records": [serialize_task_record_compact(row) for row in task_rows], "analyst_pipeline": pipeline}


def enqueue_nexus(record: TaskRecord, investigation_id: str, target: str, mode: str) -> str:
    celery = run_nexusrecon_task.delay(record.id, investigation_id, target, mode)
    return celery.id


async def publish_log(task_id: str, message: dict[str, Any]) -> None:
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    encoded = json.dumps(message, default=str)
    await redis.lpush(f"logs:{task_id}:history", encoded)
    await redis.ltrim(f"logs:{task_id}:history", 0, 499)
    await redis.publish(f"logs:{task_id}", encoded)
    await redis.aclose()


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="NexusIntel OSINT Platform",
    version="2.0.0",
    description="Standalone OSINT investigation gateway with graph storage, Celery transforms, and live log streaming.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if ALLOWED_ORIGINS == ["*"] else ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def audit_middleware(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/") and request.url.path not in {"/api/health", "/api/v1/health"}:
        auth = request.headers.get("authorization", "")
        user_id = "anonymous"
        if auth.lower().startswith("bearer "):
            try:
                user_id = verify_token(auth.split(" ", 1)[1].strip())
            except Exception:
                user_id = "invalid-token"
        try:
            with SessionLocal() as db:
                db.add(
                    AuditLog(
                        id=str(uuid.uuid4()),
                        user_id=user_id,
                        action=f"{request.method} {request.url.path}",
                        target_entity=request.path_params.get("node_id") or request.path_params.get("investigation_id"),
                        ip_address=request.client.host if request.client else None,
                        method=request.method,
                        path=request.url.path,
                        status_code=str(response.status_code),
                        meta={"query": str(request.url.query or "")},
                    )
                )
                db.commit()
        except Exception:
            pass
    return response


@app.get("/api/health")
@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "nexusintel-api", "time": now_iso()}




def default_settings() -> dict[str, Any]:
    return {
        "llm": {
            "provider": os.getenv("NEXUS_LLM_PROVIDER", "local"),
            "endpoint": os.getenv("NEXUS_LLM_ENDPOINT", "http://localhost:11434"),
            "model": os.getenv("NEXUS_LLM_MODEL", "llama3.1"),
            "api_key": os.getenv("NEXUS_LLM_API_KEY", ""),
        },
        "api_keys": {
            "github": os.getenv("GITHUB_TOKEN", ""),
            "hibp": os.getenv("HIBP_API_KEY", ""),
            "urlscan": os.getenv("URLSCAN_API_KEY", ""),
            "google_maps": os.getenv("GOOGLE_MAPS_API_KEY", ""),
            "shodan": os.getenv("SHODAN_API_KEY", ""),
            "censys": os.getenv("CENSYS_API_KEY", ""),
            "intelx": os.getenv("INTELX_API_KEY", ""),
            "virustotal": os.getenv("VIRUSTOTAL_API_KEY", ""),
            "twilio": os.getenv("TWILIO_LOOKUP_API_KEY", ""),
            "numverify": os.getenv("NUMVERIFY_API_KEY", ""),
        },
    }


def get_settings(db: Session) -> dict[str, Any]:
    record = db.get(SettingRecord, "runtime")
    if not record:
        return default_settings()
    merged = default_settings()
    value = record.value or {}
    merged["llm"] = {**merged.get("llm", {}), **(value.get("llm") or {})}
    merged["api_keys"] = {**merged.get("api_keys", {}), **(value.get("api_keys") or {})}
    return merged


def serialize_case(item: Investigation) -> dict[str, Any]:
    return {
        "id": item.id,
        "target": item.target,
        "target_type": item.target_type,
        "status": item.status,
        "mode": item.mode,
        "created_at": item.created_at.isoformat() + "Z",
        "updated_at": item.updated_at.isoformat() + "Z",
        "meta": item.meta or {},
    }


def graph_metrics(graph_state: dict[str, Any]) -> dict[str, Any]:
    nodes = graph_state.get("nodes") or []
    edges = graph_state.get("edges") or []
    by_type: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    edge_types: dict[str, int] = {}
    high_conf_ips: list[str] = []
    high_conf_domains: list[str] = []
    weak_nodes: list[dict[str, Any]] = []
    for edge in edges:
        if isinstance(edge, dict):
            edge_type = str(edge.get("type") or edge.get("label") or "RELATED_TO").upper()
            edge_types[edge_type] = edge_types.get(edge_type, 0) + 1
    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = str(node.get("type") or node.get("nodeType") or "unknown")
        label = str(node.get("label") or node.get("nodeLabel") or node.get("value") or "unknown")
        value = str(node.get("value") or label)
        node_data = node.get("data") if isinstance(node.get("data"), dict) else node.get("nodeProperties", {}) if isinstance(node.get("nodeProperties"), dict) else {}
        confidence = str(node.get("confidence") or node_data.get("confidence") or "medium").lower()
        by_type[node_type] = by_type.get(node_type, 0) + 1
        by_confidence[confidence] = by_confidence.get(confidence, 0) + 1
        if node_type == "ip" and confidence in {"confirmed", "high"}:
            high_conf_ips.append(value)
        if node_type == "domain" and confidence in {"confirmed", "high"}:
            high_conf_domains.append(value)
        if confidence in {"low", "candidate", "weak"}:
            weak_nodes.append({"id": node.get("id"), "type": node_type, "label": label, "value": value, "confidence": confidence})
    return {
        "nodes": len(nodes),
        "edges": len(edges),
        "by_type": by_type,
        "by_confidence": by_confidence,
        "edge_types": edge_types,
        "high_conf_ips": high_conf_ips[:25],
        "high_conf_domains": high_conf_domains[:25],
        "weak_nodes": weak_nodes[:25],
    }


def recommended_transforms_for_node(node: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not node:
        return [{"type": "suggest_transform", "transform": "full_identity_pipeline", "reason": "No active node; run a broad identity machine from the primary target."}]
    node_type = str(node.get("type") or node.get("nodeType") or "unknown").lower()
    mapping = {
        "username": [("maigret_username", "Enumerate public profile presence"), ("full_identity_pipeline", "Cascade handle to profiles and infrastructure")],
        "name": [("full_identity_pipeline", "Generate identity pivots from the name")],
        "email": [("email_footprint", "Resolve mailbox domain, MX, DMARC and avatar pivots"), ("full_identity_pipeline", "Cascade mailbox to username and domain pivots")],
        "domain": [("domain_recon", "Resolve DNS/RDAP/certificate pivots"), ("workspace_recon", "Map public mail/workspace posture")],
        "ip": [("ip_recon", "Collect reverse DNS and RDAP allocation"), ("reverse_dns", "Pivot from IP to hostnames")],
        "phone": [("phone_recon", "Validate E.164 and public numbering-plan hints")],
        "profile": [("maigret_username", "Re-check extracted handle across public surfaces"), ("full_identity_pipeline", "Cascade profile to identity machine")],
    }
    return [{"type": "suggest_transform", "transform": transform, "reason": reason} for transform, reason in mapping.get(node_type, [("network_recon", "Run a conservative public infrastructure pivot")])]


def fallback_oracle(prompt: str, graph_state: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    lowered = prompt.lower()
    metrics = graph_metrics(graph_state)
    intelligence = build_graph_intelligence(graph_state)
    commands: list[dict[str, Any]] = []
    if "clear" in lowered and "highlight" in lowered:
        commands.append({"type": "clear_highlight"})
    elif "ip" in lowered or "infrastructure" in lowered:
        commands.append({"type": "highlight_type", "nodeType": "ip", "minConfidence": 80 if "high" in lowered else 0})
    elif "email" in lowered or "mail" in lowered:
        commands.append({"type": "highlight_type", "nodeType": "email"})
    elif "domain" in lowered or "dns" in lowered:
        commands.append({"type": "highlight_type", "nodeType": "domain"})
    elif "profile" in lowered or "social" in lowered or "username" in lowered or "identity" in lowered:
        commands.append({"type": "highlight_type", "nodeType": "profile" if "profile" in lowered else "username"})

    if any(term in lowered for term in ["next", "transform", "pivot", "what should", "lanjut", "berikut"]):
        commands.extend(recommended_transforms_for_node(node))

    node_label = ""
    if node:
        node_label = f" Active node: {node.get('label') or node.get('value')} ({node.get('type')})."

    gaps = []
    by_type = metrics["by_type"]
    if by_type.get("domain", 0) and not by_type.get("ip", 0):
        gaps.append("domain nodes exist but no IP resolution is present")
    if by_type.get("email", 0) and not by_type.get("service", 0):
        gaps.append("email nodes exist but workspace/service posture is thin")
    if by_type.get("username", 0) and not by_type.get("profile", 0):
        gaps.append("username nodes exist but public profile confirmation is thin")
    if metrics["weak_nodes"]:
        gaps.append(f"{len(metrics['weak_nodes'])} low-confidence nodes need verification")

    recommended = recommended_transforms_for_node(node)
    reply = (
        f"Investigation posture: {metrics['nodes']} entities, {metrics['edges']} relationships. "
        f"Entity distribution: {metrics['by_type']}. Confidence distribution: {metrics['by_confidence']}."
        f" High-confidence IPs: {metrics['high_conf_ips'] or 'none'}. High-confidence domains: {metrics['high_conf_domains'] or 'none'}."
        f"{node_label} Recommended next transforms: {[item['transform'] for item in recommended]}."
        f" Collection gaps: {gaps or ['no obvious structural gaps from current graph']}."
        f" Risk posture: {intelligence['posture']} ({intelligence['risk_score']}%). Source reliability: {intelligence['source_reliability']}%."
        f" Top leads: {[lead['action'] for lead in intelligence['lead_queue'][:3]]}."
    )
    if commands:
        reply += " UI command(s) emitted for graph focus or next-action hints."
    return {"reply": reply, "commands": commands, "metrics": metrics, "intelligence": intelligence, "provider": "local_investigation_rules"}


async def llm_oracle(settings: dict[str, Any], prompt: str, graph_state: dict[str, Any], node: dict[str, Any] | None) -> dict[str, Any]:
    provider = str((settings.get("llm") or {}).get("provider") or "local").lower()
    if provider in {"local", "rules", "none"}:
        return fallback_oracle(prompt, graph_state, node)

    system = (
        "You are the NexusIntel Tactical Oracle, an elite Cyber Intelligence Analyst and OSINT investigator. "
        "You are an analyst assistant, not a judge. Analyze graph data, identify OPSEC failures, map centers of gravity, and brief tersely. "
        "Use military-style intelligence language with concise bullets for tactical recommendations. "
        "Highlight Centers of Gravity: nodes with many relationships or high-confidence infrastructure. "
        "Suggest specific lawful OSINT pivots from the provided graph only, such as MX/workspace enumeration when mail posture appears important, "
        "or technical background assessment when usernames overlap on developer/security platforms. "
        "Do not invent findings, do not declare guilt, do not assert identity certainty without direct corroborated evidence, do not claim private access, do not recommend password-reset or notification-triggering actions, and do not use emojis. "
        "Return strict JSON with keys reply and commands. "
        "Commands may include {type:'highlight_type', nodeType:'ip|domain|email|username|profile|crypto_wallet|location', minConfidence?:number}, "
        "{type:'clear_highlight'}, or {type:'suggest_transform', transform:'domain_recon|email_footprint|check_email_registrations|google_footprint_lookup|maigret_username|phone_recon|full_identity_pipeline|check_wallet_balance|trace_transactions', reason:string}. "
        "Distinguish confirmed, weak, and missing evidence."
    )
    metrics = graph_metrics(graph_state)
    intelligence = build_graph_intelligence(graph_state)
    compact_graph = {"metrics": metrics, "intelligence": intelligence, "active_node": node}
    user_prompt = f"Prompt: {prompt}\nGraph: {json.dumps(compact_graph, default=str)[:12000]}"
    endpoint = str((settings.get("llm") or {}).get("endpoint") or "").rstrip("/")
    model = str((settings.get("llm") or {}).get("model") or "llama3.1")
    api_key = str((settings.get("llm") or {}).get("api_key") or "")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            if provider == "ollama":
                response = await client.post(f"{endpoint}/api/chat", json={"model": model, "stream": False, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}]})
                response.raise_for_status()
                content = response.json().get("message", {}).get("content", "")
            elif provider == "openai":
                response = await client.post(
                    f"{endpoint or 'https://api.openai.com/v1'}/chat/completions",
                    headers={"Authorization": f"Bearer {api_key}"},
                    json={"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_prompt}], "temperature": 0.1},
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
            else:
                return fallback_oracle(prompt, graph_state, node)
        try:
            parsed = json.loads(content)
            if isinstance(parsed, dict) and "reply" in parsed:
                parsed.setdefault("commands", [])
                parsed.setdefault("metrics", metrics)
                parsed.setdefault("intelligence", intelligence)
                parsed.setdefault("provider", provider)
                return parsed
        except Exception:
            pass
        return {"reply": content or "Oracle returned an empty response.", "commands": [], "metrics": metrics, "intelligence": intelligence, "provider": provider}
    except Exception as exc:
        fallback = fallback_oracle(prompt, graph_state, node)
        fallback["reply"] = f"Configured LLM failed ({exc}). " + fallback["reply"]
        fallback["provider"] = "fallback_after_llm_error"
        return fallback


@app.post("/api/v1/auth/login", response_model=ApiResponse)
def login(payload: LoginRequest) -> ApiResponse:
    if not hmac.compare_digest(payload.username, AUTH_USER) or not hmac.compare_digest(payload.password, AUTH_PASSWORD):
        raise HTTPException(status_code=401, detail="Invalid local credentials")
    return ApiResponse(ok=True, data={"token": encode_token(payload.username), "user": payload.username})


@app.get("/api/v1/auth/me", response_model=ApiResponse)
def me(operator: str = Depends(current_operator)) -> ApiResponse:
    return ApiResponse(ok=True, data={"user": operator, "auth": "local"})


@app.get("/api/v1/cases", response_model=ApiResponse)
def list_cases(db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    items = db.execute(select(Investigation).order_by(Investigation.updated_at.desc())).scalars().all()
    return ApiResponse(ok=True, data={"items": [serialize_case(item) for item in items]})


@app.patch("/api/v1/cases/{investigation_id}", response_model=ApiResponse)
def update_case(investigation_id: str, payload: CaseUpdate, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Case not found")
    meta = dict(investigation.meta or {})
    if payload.case_name is not None:
        meta["case_name"] = payload.case_name
    if payload.assigned_operator is not None:
        meta["assigned_operator"] = payload.assigned_operator
    if payload.notes is not None:
        meta["notes"] = payload.notes
    investigation.meta = meta
    investigation.updated_at = datetime.utcnow()
    db.commit()
    return ApiResponse(ok=True, data={"case": serialize_case(investigation)})


@app.get("/api/v1/settings", response_model=ApiResponse)
def read_settings(db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    return ApiResponse(ok=True, data={"settings": get_settings(db)})


@app.put("/api/v1/settings", response_model=ApiResponse)
def write_settings(payload: SettingsUpdate, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    record = db.get(SettingRecord, "runtime")
    if not record:
        record = SettingRecord(key="runtime", value=payload.settings)
        db.add(record)
    else:
        record.value = payload.settings
        record.updated_at = datetime.utcnow()
    db.commit()
    return ApiResponse(ok=True, data={"settings": get_settings(db)})


@app.post("/api/v1/oracle/chat", response_model=ApiResponse)
async def oracle_chat(payload: OracleChatRequest, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    result = await llm_oracle(get_settings(db), payload.prompt, payload.graph_state, payload.node)
    return ApiResponse(ok=True, data=result)


@app.post("/api/v1/oracle/briefing", response_model=ApiResponse)
async def oracle_briefing(payload: OracleBriefingRequest, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    metrics = graph_metrics(payload.graph_state)
    prompt = "Generate an executive summary and threat assessment for this OSINT graph."
    oracle = await llm_oracle(get_settings(db), prompt, payload.graph_state, None)
    executive = oracle.get("reply") or f"This workspace has {metrics['nodes']} entities and {metrics['edges']} relationships across {metrics['by_type']}."
    threat = f"Confidence-weighted review: prioritize high-confidence IP/domain infrastructure, then validate low-confidence profile candidates. Current high-confidence IPs: {metrics['high_conf_ips'] or 'none observed'}."
    return ApiResponse(ok=True, data={"executive_summary": executive, "threat_assessment": threat, "metrics": metrics})

@app.post("/api/v1/investigations", response_model=ApiResponse)
async def create_investigation(payload: InvestigationCreate, db: Session = Depends(get_db)) -> ApiResponse:
    target = payload.target.strip()
    target_type = payload.target_type or classify_target(target)
    investigation = Investigation(
        id=str(uuid.uuid4()),
        target=target,
        target_type=target_type,
        status="ready",
        mode=payload.mode,
        meta={"created_by": "api", "target_type": target_type},
    )
    db.add(investigation)
    root = upsert_entity(
        db,
        investigation.id,
        type_=target_type,
        label=target,
        value=target,
        source="investigator",
        confidence="confirmed",
        data={"role": "root", "created_at": now_iso()},
    )
    db.commit()
    return ApiResponse(ok=True, data={"investigation": investigation.id, "investigation_id": investigation.id, "root_node": serialize_entity(root), "graph": graph_payload(db, investigation.id)})


@app.get("/api/v1/investigations", response_model=ApiResponse)
def list_investigations(db: Session = Depends(get_db)) -> ApiResponse:
    investigations = db.execute(select(Investigation).order_by(Investigation.created_at.desc())).scalars().all()
    return ApiResponse(
        ok=True,
        data={
            "items": [
                {
                    "id": item.id,
                    "target": item.target,
                    "target_type": item.target_type,
                    "status": item.status,
                    "mode": item.mode,
                    "created_at": item.created_at.isoformat() + "Z",
                    "updated_at": item.updated_at.isoformat() + "Z",
                    "meta": item.meta or {},
                }
                for item in investigations
            ]
        },
    )


@app.get("/api/v1/investigations/{investigation_id}/graph", response_model=ApiResponse)
def get_graph(investigation_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return ApiResponse(ok=True, data=graph_payload(db, investigation_id))



@app.get("/api/v1/investigations/{investigation_id}/leads", response_model=ApiResponse)
def investigation_leads(investigation_id: str, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return ApiResponse(ok=True, data={"items": graph_payload(db, investigation_id).get("leads", [])})


@app.get("/api/v1/investigations/{investigation_id}/noise", response_model=ApiResponse)
def investigation_noise(investigation_id: str, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return ApiResponse(ok=True, data={"items": graph_payload(db, investigation_id).get("noise", [])})


@app.get("/api/v1/investigations/{investigation_id}/compliance", response_model=ApiResponse)
def investigation_compliance(investigation_id: str, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return ApiResponse(ok=True, data={"items": graph_payload(db, investigation_id).get("compliance", [])})


@app.post("/api/v1/investigations/{investigation_id}/leads/{lead_id}/promote", response_model=ApiResponse)
def promote_lead(investigation_id: str, lead_id: str, db: Session = Depends(get_db), operator: str = Depends(current_operator)) -> ApiResponse:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    record = pop_meta_record(investigation, "leads", lead_id)
    if not record:
        raise HTTPException(status_code=404, detail="Lead not found")
    entity = entity_from_artifact_record(db, investigation_id, record, promoted=True)
    parent_id = record.get("parent_id")
    if parent_id and parent_id != entity.id and db.get(Entity, str(parent_id)):
        upsert_relationship(
            db,
            investigation_id,
            source_id=str(parent_id),
            target_id=entity.id,
            type_=str(record.get("relationship") or "PROMOTED_LEAD"),
            source="analyst_promotion",
            confidence=str(record.get("confidence") or "weak"),
            data={"promotion_status": "promoted", "lead_id": lead_id, "operator": operator},
        )
    db.add(Event(id=str(uuid.uuid4()), investigation_id=investigation_id, task_id=None, level="info", message=f"Lead promoted to graph: {entity.label}", payload={"lead": record, "entity_id": entity.id, "operator": operator}))
    db.commit()
    return ApiResponse(ok=True, data={"node": serialize_entity(entity), "graph": graph_payload(db, investigation_id)})


@app.post("/api/v1/investigations/{investigation_id}/entities/{node_id}/mark-noise", response_model=ApiResponse)
def mark_entity_noise(investigation_id: str, node_id: str, payload: MarkNoiseRequest | None = None, db: Session = Depends(get_db), operator: str = Depends(current_operator)) -> ApiResponse:
    entity = db.get(Entity, node_id)
    if not entity or entity.investigation_id != investigation_id:
        raise HTTPException(status_code=404, detail="Entity not found")
    reason = (payload.reason if payload else None) or "Analyst marked this entity as noise."
    data = dict(entity.data or {})
    data.update({"artifact_class": "NOISE", "graph_visibility": "noise_bin", "noise_reason": reason, "promotion_status": "noise"})
    entity.data = data
    record = store_non_entity_artifact(
        db,
        investigation_id,
        bucket="noise",
        artifact={"type": entity.type, "label": entity.label, "value": entity.value, "source": entity.source, "confidence": entity.confidence, "noise_reason": reason, "data": data},
        classification="NOISE",
        default_source=entity.source,
        parent_id=None,
    )
    record["entity_id"] = entity.id
    investigation = db.get(Investigation, investigation_id)
    if investigation:
        investigation.meta = append_artifact_to_meta(investigation.meta or {}, "noise", record)
    db.add(Event(id=str(uuid.uuid4()), investigation_id=investigation_id, task_id=None, level="warning", message=f"Entity marked as noise: {entity.label}", payload={"entity_id": entity.id, "reason": reason, "operator": operator}))
    db.commit()
    return ApiResponse(ok=True, data={"noise": record, "graph": graph_payload(db, investigation_id)})


@app.post("/api/v1/investigations/{investigation_id}/noise/{noise_id}/restore", response_model=ApiResponse)
def restore_noise(investigation_id: str, noise_id: str, db: Session = Depends(get_db), operator: str = Depends(current_operator)) -> ApiResponse:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    record = pop_meta_record(investigation, "noise", noise_id)
    if not record:
        raise HTTPException(status_code=404, detail="Noise record not found")
    entity = db.get(Entity, str(record.get("entity_id"))) if record.get("entity_id") else None
    if entity and entity.investigation_id == investigation_id:
        data = dict(entity.data or {})
        data.update({"artifact_class": "ENTITY", "graph_visibility": "main_graph", "promotion_status": "restored"})
        data.pop("noise_reason", None)
        entity.data = data
    else:
        entity = entity_from_artifact_record(db, investigation_id, record, promoted=False)
    db.add(Event(id=str(uuid.uuid4()), investigation_id=investigation_id, task_id=None, level="info", message=f"Noise restored to graph: {entity.label}", payload={"noise": record, "entity_id": entity.id, "operator": operator}))
    db.commit()
    return ApiResponse(ok=True, data={"node": serialize_entity(entity), "graph": graph_payload(db, investigation_id)})


@app.get("/api/v1/investigations/{investigation_id}/health", response_model=ApiResponse)
def investigation_health(investigation_id: str, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    graph = graph_payload(db, investigation_id)
    report = build_case_hygiene_report(graph)
    report["intelligence"] = build_graph_intelligence(graph)
    return ApiResponse(ok=True, data={"investigation_id": investigation_id, "health": report})


@app.get("/api/v1/investigations/{investigation_id}/intelligence", response_model=ApiResponse)
def investigation_intelligence(investigation_id: str, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    graph = graph_payload(db, investigation_id)
    return ApiResponse(ok=True, data={"investigation_id": investigation_id, "intelligence": build_graph_intelligence(graph)})


@app.delete("/api/v1/investigations/{investigation_id}", response_model=ApiResponse)
def delete_investigation(investigation_id: str, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    db.delete(investigation)
    db.commit()
    return ApiResponse(ok=True, data={"deleted": investigation_id})


@app.delete("/api/v1/cases/{investigation_id}", response_model=ApiResponse)
def delete_case(investigation_id: str, db: Session = Depends(get_db), operator: str = Depends(current_operator)) -> ApiResponse:
    return delete_investigation(investigation_id, db, operator)


@app.post("/api/v1/scans/nexusrecon", response_model=ApiResponse)
async def start_nexusrecon(payload: InvestigationCreate, db: Session = Depends(get_db)) -> ApiResponse:
    created = await create_investigation(payload, db)
    investigation_id = created.data["investigation"]
    target = payload.target.strip()
    target_type = classify_target(target)
    record = create_task_record(db, investigation_id, f"nexusintel.{target_type}", target)
    if target_type == "email":
        celery = run_email_google_task.delay(record.id, investigation_id, target, payload.mode, created.data["root_node"]["id"], "email_footprint")
    elif target_type in {"domain", "ip"}:
        celery = run_domain_task.delay(record.id, investigation_id, target, payload.mode, created.data["root_node"]["id"], "network_recon")
    elif target_type == "phone":
        celery = run_phone_task.delay(record.id, investigation_id, target, payload.mode, created.data["root_node"]["id"], "phone_recon")
    else:
        celery = run_nexusrecon_task.delay(record.id, investigation_id, target, payload.mode, created.data["root_node"]["id"])
    record.celery_id = celery.id
    investigation = db.get(Investigation, investigation_id)
    investigation.status = "running"
    db.commit()
    await publish_log(
        record.id,
        {
            "task_id": record.id,
            "level": "info",
            "message": f"Queued {target_type} OSINT pipeline for {target}",
            "time": now_iso(),
        },
    )
    return ApiResponse(ok=True, data={"investigation_id": investigation_id, "task_id": record.id, "graph": graph_payload(db, investigation_id)})


@app.post("/api/v1/entities", response_model=ApiResponse)
def add_entity(payload: ManualEntityRequest, db: Session = Depends(get_db)) -> ApiResponse:
    investigation = db.get(Investigation, payload.investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    entity = upsert_entity(
        db,
        payload.investigation_id,
        type_=payload.type,
        label=payload.label,
        value=payload.value,
        source="manual",
        confidence="confirmed",
        data=payload.data,
    )
    if payload.source_id:
        upsert_relationship(
            db,
            payload.investigation_id,
            source_id=payload.source_id,
            target_id=entity.id,
            type_=payload.relationship_type,
            source="manual",
            confidence="confirmed",
        )
    db.commit()
    return ApiResponse(ok=True, data={"node": serialize_entity(entity), "graph": graph_payload(db, payload.investigation_id)})


@app.delete("/api/v1/investigations/{investigation_id}/entities/{node_id}", response_model=ApiResponse)
def delete_entity(investigation_id: str, node_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    entity = db.get(Entity, node_id)
    if not entity or entity.investigation_id != investigation_id:
        raise HTTPException(status_code=404, detail="Entity not found")
    db.query(Relationship).filter(
        Relationship.investigation_id == investigation_id,
        ((Relationship.source_id == node_id) | (Relationship.target_id == node_id)),
    ).delete(synchronize_session=False)
    db.delete(entity)
    db.commit()
    return ApiResponse(ok=True, data={"graph": graph_payload(db, investigation_id)})


@app.post("/api/v1/transforms", response_model=ApiResponse)
async def run_transform(payload: TransformRequest, db: Session = Depends(get_db)) -> ApiResponse:
    investigation = db.get(Investigation, payload.investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    node = db.get(Entity, payload.node_id)
    if not node or node.investigation_id != payload.investigation_id:
        raise HTTPException(status_code=404, detail="Node not found")

    transform = payload.transform.lower().strip()
    target = node.value
    record = create_task_record(db, payload.investigation_id, transform, target)

    if transform in {"full_identity_pipeline", "identity_macro", "email_macro", "autonomous_identity_pipeline"}:
        celery = run_full_identity_pipeline_task.delay(record.id, payload.investigation_id, target, payload.mode, payload.node_id, transform)
    elif transform in {"legacy_nexusrecon", "nexusrecon", "maigret_username", "sherlock_username", "username_presence", "username_to_email", "username_to_accounts", "username_identity_sweep", "tier_1_major_socials", "tier_2_tech_dev", "tier_3_gaming_forums", "tier_4_deep_sweep"}:
        celery = run_nexusrecon_task.delay(record.id, payload.investigation_id, target, payload.mode, payload.node_id, transform)
    elif transform in {"email_footprint", "holehe_email", "google_osint", "workspace_recon", "email_to_account", "email_to_domain", "check_email_registrations"}:
        celery = run_email_google_task.delay(record.id, payload.investigation_id, target, payload.mode, payload.node_id, transform)
    elif transform in {"google_footprint_lookup", "google_maps_reviews"}:
        celery = run_google_footprint_task.apply_async(args=[record.id, payload.investigation_id, target, payload.node_id], queue="network_io")
    elif transform in {"domain_recon", "dns_recon", "website_recon", "network_recon", "ip_recon", "reverse_dns"}:
        celery = run_domain_task.delay(record.id, payload.investigation_id, target, payload.mode, payload.node_id, transform)
    elif transform in {"phone_recon", "e164_phone", "carrier_lookup", "numbering_plan", "phone_to_email", "phone_to_account", "check_messenger_presence", "phone_public_presence"}:
        celery = run_phone_task.delay(record.id, payload.investigation_id, target, payload.mode, payload.node_id, transform)
    elif transform in {"check_wallet_balance", "trace_transactions", "crypto_wallet", "wallet_recon"}:
        celery = run_crypto_wallet_task.apply_async(args=[record.id, payload.investigation_id, target, payload.node_id], queue="network_io")
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported transform: {payload.transform}")

    record.celery_id = celery.id
    record.status = "queued"
    investigation.status = "running"
    db.commit()
    await publish_log(
        record.id,
        {
            "task_id": record.id,
            "level": "info",
            "message": f"Queued transform {transform} for {node.label}",
            "payload": {"node_id": node.id, "mode": payload.mode},
            "time": now_iso(),
        },
    )
    return ApiResponse(ok=True, data={"task_id": record.id, "investigation_id": payload.investigation_id, "transform": transform})


@app.get("/api/v1/tasks/{task_id}", response_model=ApiResponse)
def task_status(task_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    task = db.get(TaskRecord, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return ApiResponse(
        ok=True,
        data={
            "id": task.id,
            "investigation_id": task.investigation_id,
            "task_name": task.task_name,
            "status": task.status,
            "target": task.target,
            "started_at": task.started_at.isoformat() + "Z" if task.started_at else None,
            "finished_at": task.finished_at.isoformat() + "Z" if task.finished_at else None,
            "error": task.error,
            "result": task.result or {},
        },
    )


@app.get("/api/v1/tasks/{task_id}/graph", response_model=ApiResponse)
def task_graph(task_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    task = db.get(TaskRecord, task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return ApiResponse(ok=True, data=graph_payload(db, task.investigation_id))




@app.get("/api/v1/transforms/registry", response_model=ApiResponse)
def transform_registry(db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    configured = configured_osint_key_names(db)
    return ApiResponse(ok=True, data={"adapters": registry.list_adapters(), "transforms": registry.list_transforms(configured)})


@app.post("/api/v1/transforms/run", response_model=ApiResponse)
async def run_registered_transform(payload: TransformRunRequest, db: Session = Depends(get_db), operator: str = Depends(current_operator)) -> ApiResponse:
    investigation = db.get(Investigation, payload.investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    transform = registry.get_transform(payload.transform_id)
    if not transform:
        raise HTTPException(status_code=404, detail="Transform not found")
    adapter = registry.get_adapter(transform.adapter_id)
    if not adapter:
        raise HTTPException(status_code=501, detail=f"Adapter not implemented: {transform.adapter_id}")
    api_keys = osint_api_keys(db)
    missing = [key for key in transform.required_keys if key not in api_keys]
    if missing:
        raise HTTPException(status_code=409, detail=f"Missing required API key(s): {', '.join(missing)}")

    parent: Entity | None = None
    if payload.node_id:
        parent = db.get(Entity, payload.node_id)
        if not parent or parent.investigation_id != payload.investigation_id:
            raise HTTPException(status_code=404, detail="Node not found")
        entity_input = EntityInput(type=parent.type, value=parent.value, label=parent.label, entity_id=parent.id, data=parent.data or {})
    else:
        raw_input = payload.input or {}
        input_type = str(raw_input.get("type") or "").strip()
        input_value = str(raw_input.get("value") or "").strip()
        if not input_type or not input_value:
            raise HTTPException(status_code=422, detail="Transform input requires type and value when node_id is omitted")
        entity_input = EntityInput(type=input_type, value=input_value, label=str(raw_input.get("label") or input_value), data=raw_input.get("data") or {})

    if entity_input.type not in transform.input_types and "*" not in transform.input_types:
        raise HTTPException(status_code=422, detail=f"Transform {transform.id} does not accept input type {entity_input.type}")

    record = create_task_record(db, payload.investigation_id, transform.id, entity_input.value)
    record.status = "running"
    record.started_at = datetime.utcnow()
    db.flush()
    await publish_log(record.id, {"task_id": record.id, "level": "info", "message": f"Running registered transform {transform.id} via {adapter.id}", "time": now_iso()})

    context = RunContext(investigation_id=payload.investigation_id, run_id=record.id, api_keys=api_keys, options=payload.options, operator=operator)
    try:
        result = await adapter.run(entity_input, context)
        await publish_log(record.id, {"task_id": record.id, "level": "info", "message": f"Source queried: {adapter.name} ({adapter.id})", "payload": {"source": adapter.id, "result_count": len(result.artifacts)}, "time": now_iso()})
        await publish_log(record.id, {"task_id": record.id, "level": "info", "message": f"Raw evidence captured: {len(result.raw_evidence)} object(s)", "payload": {"raw_evidence_count": len(result.raw_evidence)}, "time": now_iso()})
        if result.artifacts:
            average_confidence = int(sum(item.confidence_score for item in result.artifacts) / len(result.artifacts))
            noise_filtered = len([item for item in result.artifacts if item.confidence_score < 40])
            await publish_log(record.id, {"task_id": record.id, "level": "info", "message": f"Confidence baseline updated: avg={average_confidence}% noise_filtered={noise_filtered}", "payload": {"average_confidence": average_confidence, "noise_filtered": noise_filtered}, "time": now_iso()})
        persisted = persist_adapter_result(db, payload.investigation_id, parent, result)
        record.status = "completed"
        record.finished_at = datetime.utcnow()
        record.result = {"adapter_result": result.to_dict(), "persisted": persisted}
        investigation.updated_at = datetime.utcnow()
        db.commit()
        await publish_log(record.id, {"task_id": record.id, "level": "success", "message": f"Transform {transform.id} completed with {len(result.artifacts)} artifact(s) and {len(result.raw_evidence)} evidence object(s)", "time": now_iso()})
        return ApiResponse(ok=True, data={"run_id": record.id, "status": record.status, "result": record.result, "graph": graph_payload(db, payload.investigation_id)})
    except HTTPException:
        raise
    except Exception as exc:
        record.status = "failed"
        record.finished_at = datetime.utcnow()
        record.error = str(exc)
        db.commit()
        await publish_log(record.id, {"task_id": record.id, "level": "error", "message": f"Transform {transform.id} failed: {exc}", "time": now_iso()})
        raise HTTPException(status_code=500, detail=f"Transform failed: {exc}") from exc


@app.get("/api/v1/transforms/runs/{run_id}", response_model=ApiResponse)
def transform_run_status(run_id: str, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    task = db.get(TaskRecord, run_id)
    if not task:
        raise HTTPException(status_code=404, detail="Transform run not found")
    return task_status(run_id, db)


@app.get("/api/v1/evidence/{evidence_id}", response_model=ApiResponse)
def read_evidence(evidence_id: str, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    record = db.get(DataProvenance, evidence_id)
    if not record:
        raise HTTPException(status_code=404, detail="Evidence record not found")
    verification = ProvenanceStore().verify(record.uri, record.sha256)
    return ApiResponse(ok=True, data={"evidence": serialize_provenance_record(record, include_payload=True), "verification": verification})


@app.get("/api/v1/investigations/{investigation_id}/evidence", response_model=ApiResponse)
def list_investigation_evidence(investigation_id: str, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    if not db.get(Investigation, investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    rows = db.execute(select(DataProvenance).where(DataProvenance.investigation_id == investigation_id).order_by(DataProvenance.created_at.desc())).scalars().all()
    return ApiResponse(ok=True, data={"items": [serialize_provenance_record(row) for row in rows]})


@app.get("/api/v1/evidence", response_model=ApiResponse)
def list_all_evidence(limit: int = 250, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    rows = db.execute(select(DataProvenance).order_by(DataProvenance.created_at.desc()).limit(max(1, min(1000, limit)))).scalars().all()
    return ApiResponse(ok=True, data={"items": [serialize_provenance_record(row) for row in rows]})


@app.get("/api/v1/investigations/{investigation_id}/analyst-pipeline", response_model=ApiResponse)
def analyst_pipeline(investigation_id: str, entity_id: str | None = None, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    return ApiResponse(ok=True, data=analyst_pipeline_payload(db, investigation_id, entity_id))


@app.post("/api/v1/investigations/{investigation_id}/correlate", response_model=ApiResponse)
def correlate_investigation(investigation_id: str, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    if not db.get(Investigation, investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    graph = graph_payload(db, investigation_id)
    correlations = build_correlations(graph["nodes"], graph["edges"])
    created = []
    for item in correlations:
        if int(item.get("confidence_level") or 0) < 50:
            continue
        edge = upsert_relationship(
            db,
            investigation_id,
            source_id=str(item["source"]),
            target_id=str(item["target"]),
            type_="possible_same_actor",
            source="correlation_engine",
            confidence="probable" if int(item["confidence_level"]) >= 70 else "weak",
            data={
                "confidence_level": int(item["confidence_level"]),
                "confidence_reason": "; ".join(item.get("reasons") or []),
                "shared_features": item.get("shared_features") or {},
                "legal_basis": item.get("legal_basis"),
                "requires_analyst_confirmation": True,
            },
        )
        created.append(serialize_relationship(edge))
    db.commit()
    return ApiResponse(ok=True, data={"created": created, "graph": graph_payload(db, investigation_id)})


@app.get("/api/v1/investigations/{investigation_id}/exports/analyst-packet")
def export_analyst_packet(investigation_id: str, format: Literal["html", "pdf", "json", "csv", "graph_json"] = "html", db: Session = Depends(get_db), _: str = Depends(current_operator)) -> Response:
    payload = analyst_pipeline_payload(db, investigation_id)
    case = payload["case"]
    graph = payload["graph"]
    pipeline = payload["analyst_pipeline"]
    evidence = payload["evidence"]
    filename_base = f"nexusintel-{investigation_id}-analyst-packet"
    if format == "json":
        return Response(json_packet(case, graph, pipeline, evidence), media_type="application/json", headers={"Content-Disposition": f"attachment; filename={filename_base}.json"})
    if format == "graph_json":
        return Response(json.dumps(graph, indent=2, default=str), media_type="application/json", headers={"Content-Disposition": f"attachment; filename={filename_base}-graph.json"})
    if format == "csv":
        return Response(ioc_csv(graph), media_type="text/csv", headers={"Content-Disposition": f"attachment; filename={filename_base}-iocs.csv"})
    if format == "pdf":
        lines = [
            f"Case: {case.get('target')}",
            f"Entities: {len(graph.get('nodes') or [])}",
            f"Relationships: {len(graph.get('edges') or [])}",
            f"Evidence objects: {len(evidence)}",
            f"Generated: {pipeline.get('generated_at')}",
            "Lead Queue:",
        ]
        for group, items in (pipeline.get("lead_queue") or {}).items():
            lines.append(str(group).upper())
            for item in items[:8] if isinstance(items, list) else []:
                lines.append(str(item))
        return Response(minimal_pdf("NexusIntel Analyst Packet", lines), media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename_base}.pdf"})
    return Response(html_packet(case, graph, pipeline, evidence), media_type="text/html", headers={"Content-Disposition": f"attachment; filename={filename_base}.html"})


@app.post("/api/v1/importers/preview", response_model=ApiResponse)
def preview_import(payload: ImportPreviewRequest, _: str = Depends(current_operator)) -> ApiResponse:
    preview = preview_csv(payload.content)
    mapping = spiderfoot_mapping(preview["headers"]) if payload.format == "spiderfoot_csv" else {"columns": preview["headers"], "mapping": {}, "confidence": "analyst_review_required"}
    return ApiResponse(ok=True, data={"preview": preview, "mapping": mapping, "legal_basis": "Analyst-provided import preview; no graph write until operator confirms import."})


@app.post("/api/v1/provenance", response_model=ApiResponse)
def create_provenance(payload: ProvenanceCreate, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    if not db.get(Investigation, payload.investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    stored = ProvenanceStore().put(investigation_id=payload.investigation_id, source=payload.source, content=payload.payload)
    record = DataProvenance(
        id=str(uuid.uuid4()),
        investigation_id=payload.investigation_id,
        entity_id=payload.entity_id,
        source=payload.source,
        uri=stored["uri"],
        sha256=stored["sha256"],
        content_type=stored["content_type"],
        size_bytes=str(stored["size"]),
        meta={"storage": stored["storage"]},
    )
    db.add(record)
    db.commit()
    return ApiResponse(ok=True, data={"provenance": {"id": record.id, **stored}})


@app.get("/api/v1/provenance/{provenance_id}/verify", response_model=ApiResponse)
def verify_provenance(provenance_id: str, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    record = db.get(DataProvenance, provenance_id)
    if not record:
        raise HTTPException(status_code=404, detail="Provenance record not found")
    return ApiResponse(ok=True, data={"verification": ProvenanceStore().verify(record.uri, record.sha256)})


@app.get("/api/v1/audit", response_model=ApiResponse)
def list_audit(limit: int = 100, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    rows = db.execute(select(AuditLog).order_by(AuditLog.created_at.desc()).limit(max(1, min(500, limit)))).scalars().all()
    return ApiResponse(ok=True, data={"items": [{"id": row.id, "user_id": row.user_id, "action": row.action, "target_entity": row.target_entity, "ip_address": row.ip_address, "status_code": row.status_code, "created_at": row.created_at.isoformat() + "Z"} for row in rows]})


@app.post("/api/v1/watchlist", response_model=ApiResponse)
@app.post("/api/v1/watchlists", response_model=ApiResponse)
def create_watchlist(payload: WatchlistCreate, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    investigation = db.get(Investigation, payload.investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    item = Watchlist(id=str(uuid.uuid4()), investigation_id=payload.investigation_id, target=payload.target, target_type=payload.target_type or classify_target(payload.target), enabled=str(payload.enabled).lower(), interval_hours=str(payload.interval_hours))
    db.add(item)
    db.commit()
    return ApiResponse(ok=True, data={"watchlist": {"id": item.id, "investigation_id": item.investigation_id, "target": item.target, "target_type": item.target_type, "enabled": item.enabled == "true", "interval_hours": int(item.interval_hours)}})


@app.get("/api/v1/watchlist", response_model=ApiResponse)
@app.get("/api/v1/watchlists", response_model=ApiResponse)
def list_watchlists(db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    rows = db.execute(select(Watchlist).order_by(Watchlist.updated_at.desc())).scalars().all()
    return ApiResponse(ok=True, data={"items": [{"id": row.id, "investigation_id": row.investigation_id, "target": row.target, "target_type": row.target_type, "enabled": row.enabled == "true", "interval_hours": int(row.interval_hours), "last_delta": row.last_delta or {}, "updated_at": row.updated_at.isoformat() + "Z"} for row in rows]})


@app.patch("/api/v1/watchlists/{watchlist_id}/toggle", response_model=ApiResponse)
def toggle_watchlist(watchlist_id: str, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    item = db.get(Watchlist, watchlist_id)
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    item.enabled = "false" if item.enabled == "true" else "true"
    item.updated_at = datetime.utcnow()
    db.commit()
    return ApiResponse(ok=True, data={"id": item.id, "enabled": item.enabled == "true"})


@app.delete("/api/v1/watchlist/{watchlist_id}", response_model=ApiResponse)
@app.delete("/api/v1/watchlists/{watchlist_id}", response_model=ApiResponse)
def delete_watchlist(watchlist_id: str, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    item = db.get(Watchlist, watchlist_id)
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    db.delete(item)
    db.commit()
    return ApiResponse(ok=True, data={"deleted": watchlist_id})


@app.post("/api/v1/entity-resolution/score", response_model=ApiResponse)
def score_entity_resolution(payload: EntityResolutionRequest, _: str = Depends(current_operator)) -> ApiResponse:
    async_result = run_entity_resolution_task.apply_async(args=[payload.left, payload.right], queue="ml_gpu")
    return ApiResponse(ok=True, data={"task_id": async_result.id, "queue": "ml_gpu"})


@app.post("/api/v1/collaboration/patch", response_model=ApiResponse)
def publish_collaboration_patch(payload: CollaborationPatch, operator: str = Depends(current_operator)) -> ApiResponse:
    published = CollaborationBus(REDIS_URL).publish_patch(payload.workspace_id, {**payload.patch, "operator": operator, "time": now_iso()})
    return ApiResponse(ok=True, data={"published": published, "workspace_id": payload.workspace_id})


@app.post("/api/v1/collaboration/presence", response_model=ApiResponse)
def update_presence(payload: PresenceUpdate, operator: str = Depends(current_operator)) -> ApiResponse:
    bus = CollaborationBus(REDIS_URL)
    bus.presence(payload.workspace_id, operator, {**payload.state, "operator": operator, "time": now_iso()})
    return ApiResponse(ok=True, data={"presence": bus.list_presence(payload.workspace_id)})


@app.post("/api/v1/crypto/wallet", response_model=ApiResponse)
def crypto_wallet_lookup(payload: CryptoLookupRequest, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    if not db.get(Investigation, payload.investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    record = create_task_record(db, payload.investigation_id, "crypto_wallet", payload.address)
    celery = run_crypto_wallet_task.apply_async(args=[record.id, payload.investigation_id, payload.address, payload.parent_node_id], queue="network_io")
    record.celery_id = celery.id
    db.commit()
    return ApiResponse(ok=True, data={"task_id": record.id, "queue": "network_io"})


@app.post("/api/v1/serverless/invoke", response_model=ApiResponse)
def serverless_invoke(payload: ServerlessInvokeRequest, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    if not db.get(Investigation, payload.investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    record = create_task_record(db, payload.investigation_id, "serverless_invoke", json.dumps(payload.payload, default=str)[:2048])
    celery = run_serverless_invoker_task.apply_async(args=[record.id, payload.investigation_id, payload.payload], queue="network_io")
    record.celery_id = celery.id
    db.commit()
    return ApiResponse(ok=True, data={"task_id": record.id, "queue": "network_io"})


@app.get("/api/v1/proxies/status", response_model=ApiResponse)
def proxy_status(_: str = Depends(current_operator)) -> ApiResponse:
    rotator = ProxyRotator(REDIS_URL)
    seeded = rotator.seed_from_env()
    decision = rotator.next()
    return ApiResponse(ok=True, data={"configured": seeded, "next_source": decision.source, "has_proxy": bool(decision.proxy_url)})


@app.post("/api/v1/proxies/seed", response_model=ApiResponse)
def proxy_seed(payload: ProxySeedRequest, _: str = Depends(current_operator)) -> ApiResponse:
    count = ProxyRotator(REDIS_URL).seed(payload.proxies)
    return ApiResponse(ok=True, data={"configured": count})


@app.websocket("/api/v1/ws/logs/{task_id}")
async def websocket_logs(websocket: WebSocket, task_id: str):
    await websocket.accept()
    redis = aioredis.from_url(REDIS_URL, decode_responses=True)
    pubsub = redis.pubsub()
    try:
        history = await redis.lrange(f"logs:{task_id}:history", 0, 199)
        for item in reversed(history):
            await websocket.send_text(item)

        await pubsub.subscribe(f"logs:{task_id}")
        await websocket.send_text(
            json.dumps(
                {
                    "task_id": task_id,
                    "level": "system",
                    "message": "Live OSINT telemetry connected",
                    "time": now_iso(),
                }
            )
        )
        while True:
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=20)
            if message and message.get("data"):
                await websocket.send_text(message["data"])
            else:
                await websocket.send_text(
                    json.dumps({"task_id": task_id, "level": "heartbeat", "message": "stream alive", "time": now_iso()})
                )
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(f"logs:{task_id}")
        await pubsub.close()
        await redis.aclose()
