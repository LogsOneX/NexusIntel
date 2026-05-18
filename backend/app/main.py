import json
import asyncio
import time
from datetime import datetime, timezone
from typing import Iterator

from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db, init_db
from app.events import channel_for, emit_event, redis_client
from app.graph_store import delete_entity, graph_payload, refresh_summary, upsert_entity, upsert_relationship
from app.models import Entity, Event, Investigation
from app.schemas import ExpandRequest, InvestigationCreate, InvestigationOut, LegacyNexusRequest, ManualEntityCreate
from app.targeting import classify_target, root_entity_type
from app.tasks import expand_entity, run_investigation, run_legacy_nexusrecon


settings = get_settings()
app = FastAPI(title="NexusIntel OSINT Platform", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": "nexusintel-api", "time": datetime.now(timezone.utc).isoformat()}


@app.get("/api/schema")
def schema() -> dict:
    return {
        "entity_types": [
            "target",
            "username",
            "email",
            "domain",
            "website",
            "url",
            "ip",
            "subdomain",
            "service",
            "developer_profile",
            "social_profile",
            "creator_profile",
            "identity_profile",
            "package_profile",
            "dns_record",
            "mail_server",
            "nameserver",
            "organization",
            "tracker",
            "avatar",
            "hash",
            "phone",
            "risk",
            "task",
            "signal",
        ],
        "modes": ["standard", "active", "aggressive"],
        "modules": [
            "intel_planner",
            "identity_profiler",
            "email_workspace_recon",
            "domain_recon",
            "website_surface_recon",
            "phone_recon",
            "legacy_nexusrecon_bridge",
            "legacy_analytics_bridge",
        ],
        "guardrails": [
            "public-source only",
            "no credential stuffing",
            "no private API abuse",
            "no password reset or registration probing",
            "read-only active checks for authorized assets",
        ],
    }


@app.post("/api/investigations", response_model=InvestigationOut)
def create_investigation(payload: InvestigationCreate, db: Session = Depends(get_db)) -> Investigation:
    target = payload.target.strip()
    target_type = classify_target(target)
    investigation = Investigation(target=target, target_type=target_type, mode=payload.mode, status="queued")
    db.add(investigation)
    db.flush()
    root = upsert_entity(
        db,
        investigation.id,
        root_entity_type(target_type),
        target,
        target,
        100,
        "target",
        {"mode": payload.mode, "target_type": target_type},
    )
    investigation.summary = {"nodes": 1, "edges": 0, "types": {root.type: 1}}
    db.commit()
    db.refresh(investigation)
    emit_event(investigation.id, "info", f"Queued {target_type} investigation for {target}", "api")
    run_investigation.delay(investigation.id)
    return investigation


@app.get("/api/investigations", response_model=list[InvestigationOut])
def list_investigations(db: Session = Depends(get_db)) -> list[Investigation]:
    return list(db.scalars(select(Investigation).order_by(desc(Investigation.created_at)).limit(100)).all())


@app.get("/api/investigations/{investigation_id}", response_model=InvestigationOut)
def get_investigation(investigation_id: str, db: Session = Depends(get_db)) -> Investigation:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return investigation


@app.get("/api/investigations/{investigation_id}/graph")
def get_graph(investigation_id: str, db: Session = Depends(get_db)) -> dict:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return graph_payload(db, investigation_id)


@app.get("/api/investigations/{investigation_id}/events")
def stream_events(investigation_id: str, db: Session = Depends(get_db)) -> StreamingResponse:
    if not db.get(Investigation, investigation_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    historical = db.scalars(
        select(Event).where(Event.investigation_id == investigation_id).order_by(Event.created_at).limit(250)
    ).all()

    def generate() -> Iterator[str]:
        for event in historical:
            yield _sse(
                {
                    "id": event.id,
                    "level": event.level,
                    "message": event.message,
                    "module": event.module,
                    "payload": event.payload or {},
                    "created_at": event.created_at.isoformat(),
                }
            )

        pubsub = redis_client.pubsub()
        pubsub.subscribe(channel_for(investigation_id))
        try:
            while True:
                message = pubsub.get_message(ignore_subscribe_messages=True, timeout=20)
                if message and message.get("data"):
                    yield _sse(json.loads(message["data"]))
                else:
                    yield ": heartbeat\n\n"
                time.sleep(0.25)
        finally:
            pubsub.unsubscribe(channel_for(investigation_id))
            pubsub.close()

    return StreamingResponse(generate(), media_type="text/event-stream")


@app.post("/api/investigations/{investigation_id}/expand")
def expand_selected_entity(investigation_id: str, payload: ExpandRequest, db: Session = Depends(get_db)) -> dict:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    entity = db.get(Entity, payload.entity_id)
    if not entity or entity.investigation_id != investigation_id:
        raise HTTPException(status_code=404, detail="Entity not found")
    task = expand_entity.delay(investigation_id, payload.entity_id, payload.mode or investigation.mode)
    emit_event(investigation_id, "info", f"Queued expansion for {entity.label}", "api", {"task_id": task.id})
    return {"status": "queued", "task_id": task.id}


@app.post("/api/investigations/{investigation_id}/legacy/nexusrecon")
def launch_legacy_nexusrecon(investigation_id: str, payload: LegacyNexusRequest, db: Session = Depends(get_db)) -> dict:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    target = (payload.target or investigation.target).strip()
    mode = payload.mode or investigation.mode
    task = run_legacy_nexusrecon.delay(investigation_id, target, mode)
    emit_event(
        investigation_id,
        "info",
        f"Queued legacy NexusRecon bridge for {target}.",
        "api",
        {"task_id": task.id, "mode": mode},
    )
    return {"status": "queued", "task_id": task.id, "target": target, "mode": mode}


@app.post("/api/investigations/{investigation_id}/entities")
def add_manual_entity(investigation_id: str, payload: ManualEntityCreate, db: Session = Depends(get_db)) -> dict:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    manual = upsert_entity(
        db,
        investigation_id,
        payload.type.strip().lower(),
        payload.value.strip(),
        payload.label or payload.value.strip(),
        payload.confidence,
        "manual",
        payload.properties,
    )
    if payload.source_entity_id:
        source = db.get(Entity, payload.source_entity_id)
        if source and source.investigation_id == investigation_id:
            upsert_relationship(
                db,
                investigation_id,
                source,
                manual,
                payload.relationship_type,
                payload.relationship_type.replace("_", " ").title(),
                min(100, max(0, payload.confidence)),
                {"source": "manual"},
            )
    refresh_summary(db, investigation)
    db.commit()
    emit_event(investigation_id, "info", f"Manual entity added: {manual.label}", "api", {"entity_id": manual.id})
    return {"status": "saved", "entity": {"id": manual.id, "label": manual.label, "type": manual.type}}


@app.delete("/api/investigations/{investigation_id}/entities/{entity_id}")
def remove_entity(investigation_id: str, entity_id: str, db: Session = Depends(get_db)) -> dict:
    investigation = db.get(Investigation, investigation_id)
    if not investigation:
        raise HTTPException(status_code=404, detail="Investigation not found")
    deleted = delete_entity(db, investigation_id, entity_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Entity not found")
    refresh_summary(db, investigation)
    db.commit()
    emit_event(investigation_id, "info", f"Entity removed: {entity_id}", "api")
    return {"status": "deleted"}


def _sse(data: dict) -> str:
    return f"event: log\ndata: {json.dumps(data, default=str)}\n\n"


@app.websocket("/api/investigations/{investigation_id}/ws")
async def websocket_events(websocket: WebSocket, investigation_id: str) -> None:
    await websocket.accept()
    pubsub = redis_client.pubsub()
    pubsub.subscribe(channel_for(investigation_id))
    try:
        for event in _historical_events(investigation_id):
            await websocket.send_json(event)
        while True:
            message = await asyncio.to_thread(pubsub.get_message, True, 5)
            if message and message.get("data"):
                await websocket.send_json(json.loads(message["data"]))
            else:
                await websocket.send_json({"level": "heartbeat", "message": "keepalive", "module": "ws"})
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        return
    finally:
        pubsub.unsubscribe(channel_for(investigation_id))
        pubsub.close()


def _historical_events(investigation_id: str) -> list[dict]:
    from app.database import SessionLocal

    with SessionLocal() as session:
        events = session.scalars(
            select(Event).where(Event.investigation_id == investigation_id).order_by(Event.created_at).limit(250)
        ).all()
        return [
            {
                "id": event.id,
                "level": event.level,
                "message": event.message,
                "module": event.module,
                "payload": event.payload or {},
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ]
