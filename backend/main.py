from __future__ import annotations

import json
import os
import uuid
import ipaddress
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Literal

import redis.asyncio as aioredis
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, declarative_base, relationship, sessionmaker

from tasks import run_domain_task, run_email_google_task, run_nexusrecon_task, run_phone_task


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://nexus:nexus@postgres:5432/nexusintel",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")
ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")]


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


class ApiResponse(BaseModel):
    ok: bool
    data: dict[str, Any] = Field(default_factory=dict)


def get_db() -> Session:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


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
        existing.data = {**(existing.data or {}), **(data or {})}
        return existing

    edge = Relationship(
        id=str(uuid.uuid4()),
        investigation_id=investigation_id,
        source_id=source_id,
        target_id=target_id,
        type=type_,
        source=source,
        confidence=confidence,
        data=data or {},
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


@app.get("/api/health")
@app.get("/api/v1/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "nexusintel-api", "time": now_iso()}


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
    return ApiResponse(ok=True, data={"investigation": investigation.id, "root_node": serialize_entity(root)})


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

    if transform in {"legacy_nexusrecon", "nexusrecon", "maigret_username", "sherlock_username", "username_presence"}:
        celery = run_nexusrecon_task.delay(record.id, payload.investigation_id, target, payload.mode, payload.node_id)
    elif transform in {"email_footprint", "holehe_email", "google_osint", "workspace_recon"}:
        celery = run_email_google_task.delay(record.id, payload.investigation_id, target, payload.mode, payload.node_id, transform)
    elif transform in {"domain_recon", "dns_recon", "website_recon", "network_recon", "ip_recon", "reverse_dns"}:
        celery = run_domain_task.delay(record.id, payload.investigation_id, target, payload.mode, payload.node_id, transform)
    elif transform in {"phone_recon", "e164_phone", "carrier_lookup", "numbering_plan"}:
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
