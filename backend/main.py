from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import uuid
import ipaddress
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Literal

import redis.asyncio as aioredis
import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

from tasks import run_crypto_wallet_task, run_domain_task, run_email_google_task, run_entity_resolution_task, run_full_identity_pipeline_task, run_nexusrecon_task, run_phone_task, run_serverless_invoker_task
from backend.modules.case_hygiene import build_case_hygiene_report
from backend.modules.graph_intel import build_graph_intelligence
from backend.modules.collaboration_bus import CollaborationBus
from backend.modules.provenance_store import ProvenanceStore
from backend.modules.proxy_rotator import ProxyRotator


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


class ManualEntityRequest(BaseModel):
    investigation_id: str
    type: str = Field(..., min_length=2, max_length=64)
    label: str = Field(..., min_length=1, max_length=512)
    value: str = Field(..., min_length=1, max_length=2048)
    source_id: str | None = None
    relationship_type: str = "manual_link"
    data: dict[str, Any] = Field(default_factory=dict)


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


def graph_payload(db: Session, investigation_id: str) -> dict[str, Any]:
    entities = db.execute(select(Entity).where(Entity.investigation_id == investigation_id)).scalars().all()
    relationships = db.execute(select(Relationship).where(Relationship.investigation_id == investigation_id)).scalars().all()
    return {
        "nodes": [serialize_entity(entity) for entity in entities],
        "edges": [serialize_relationship(edge) for edge in relationships],
    }


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
            "shodan": os.getenv("SHODAN_API_KEY", ""),
            "intelx": os.getenv("INTELX_API_KEY", ""),
            "virustotal": os.getenv("VIRUSTOTAL_API_KEY", ""),
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
        "You are NexusIntel Oracle, a senior OSINT investigation copilot. "
        "Analyze only the supplied graph JSON and active node. Be concise, operational, and evidence-aware. "
        "Return strict JSON with keys reply and commands. "
        "Commands may include {type:'highlight_type', nodeType:'ip|domain|email|username|profile', minConfidence?:number}, "
        "{type:'clear_highlight'}, or {type:'suggest_transform', transform:'domain_recon|email_footprint|maigret_username|phone_recon|full_identity_pipeline', reason:string}. "
        "Do not invent findings; distinguish confirmed, weak, and missing evidence."
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
    elif transform in {"legacy_nexusrecon", "nexusrecon", "maigret_username", "sherlock_username", "username_presence", "username_to_email", "username_to_accounts", "tier_1_major_socials", "tier_2_tech_dev", "tier_3_gaming_forums", "tier_4_deep_sweep"}:
        celery = run_nexusrecon_task.delay(record.id, payload.investigation_id, target, payload.mode, payload.node_id, transform)
    elif transform in {"email_footprint", "holehe_email", "google_osint", "workspace_recon", "email_to_account", "email_to_domain"}:
        celery = run_email_google_task.delay(record.id, payload.investigation_id, target, payload.mode, payload.node_id, transform)
    elif transform in {"domain_recon", "dns_recon", "website_recon", "network_recon", "ip_recon", "reverse_dns"}:
        celery = run_domain_task.delay(record.id, payload.investigation_id, target, payload.mode, payload.node_id, transform)
    elif transform in {"phone_recon", "e164_phone", "carrier_lookup", "numbering_plan", "phone_to_email", "phone_to_account"}:
        celery = run_phone_task.delay(record.id, payload.investigation_id, target, payload.mode, payload.node_id, transform)
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


@app.post("/api/v1/watchlists", response_model=ApiResponse)
def create_watchlist(payload: WatchlistCreate, db: Session = Depends(get_db), _: str = Depends(current_operator)) -> ApiResponse:
    investigation = db.get(Investigation, payload.investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    item = Watchlist(id=str(uuid.uuid4()), investigation_id=payload.investigation_id, target=payload.target, target_type=payload.target_type or classify_target(payload.target), enabled=str(payload.enabled).lower(), interval_hours=str(payload.interval_hours))
    db.add(item)
    db.commit()
    return ApiResponse(ok=True, data={"watchlist": {"id": item.id, "investigation_id": item.investigation_id, "target": item.target, "target_type": item.target_type, "enabled": item.enabled == "true", "interval_hours": int(item.interval_hours)}})


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
