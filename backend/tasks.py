from __future__ import annotations

import asyncio
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import socket
import sys
import uuid
from dataclasses import asdict, is_dataclass
from datetime import datetime
from typing import Any

import dns.resolver
import httpx
import redis
from celery import Celery
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from recon_validators import analyze_email_target, analyze_identity_target, analyze_network_target, analyze_phone_target, normalize_username
from backend.modules.email_recon import EmailPresenceResolver
from backend.modules.identity_recon import IdentityResolver
from backend.modules.phone_recon import PhoneResolver


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://nexus:nexus@postgres:5432/nexusintel",
)
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


celery_app = Celery("nexusintel", broker=REDIS_URL, backend=REDIS_URL)
celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    worker_prefetch_multiplier=1,
    task_time_limit=int(os.getenv("TASK_TIME_LIMIT", "1800")),
    task_soft_time_limit=int(os.getenv("TASK_SOFT_TIME_LIMIT", "1500")),
)


engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
Base = declarative_base()
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)


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


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def task_session() -> Session:
    Base.metadata.create_all(bind=engine)
    return SessionLocal()


def emit(task_id: str, level: str, message: str, payload: dict[str, Any] | None = None, investigation_id: str | None = None) -> None:
    envelope = {
        "task_id": task_id,
        "level": level,
        "message": message.strip(),
        "payload": payload or {},
        "time": now_iso(),
    }
    encoded = json.dumps(envelope, default=str)
    redis_client.lpush(f"logs:{task_id}:history", encoded)
    redis_client.ltrim(f"logs:{task_id}:history", 0, 499)
    redis_client.publish(f"logs:{task_id}", encoded)
    if investigation_id:
        with task_session() as db:
            db.add(
                Event(
                    id=str(uuid.uuid4()),
                    investigation_id=investigation_id,
                    task_id=task_id,
                    level=level,
                    message=message.strip(),
                    payload=payload or {},
                )
            )
            db.commit()


def fingerprint(kind: str, value: str) -> str:
    return f"{kind}:{value.strip().lower()}"[:768]


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
        existing.label = label or existing.label
        existing.source = source or existing.source
        existing.confidence = confidence or existing.confidence
        existing.data = {**(existing.data or {}), **(data or {})}
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
    db.flush()
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
    db.flush()
    return edge


def persist_artifacts(
    db: Session,
    investigation_id: str,
    parent: Entity,
    artifacts: list[dict[str, Any]],
    default_source: str,
) -> list[str]:
    created_ids: list[str] = []
    for artifact in artifacts:
        node_type = str(artifact.get("type") or "signal")
        label = str(artifact.get("label") or artifact.get("value") or node_type)
        value = str(artifact.get("value") or label)
        source = str(artifact.get("source") or default_source)
        confidence = str(artifact.get("confidence") or "medium")
        artifact_data = dict(artifact.get("data") or {})
        artifact_data["artifact"] = {
            "source": source,
            "relationship": artifact.get("relationship") or "derived_signal",
            "confidence": confidence,
        }
        node = upsert_entity(
            db,
            investigation_id,
            type_=node_type,
            label=label,
            value=value,
            source=source,
            confidence=confidence,
            data=artifact_data,
        )
        if node.id != parent.id:
            upsert_relationship(
                db,
                investigation_id,
                source_id=parent.id,
                target_id=node.id,
                type_=str(artifact.get("relationship") or "derived_signal"),
                source=source,
                confidence=confidence,
                data={"validator": default_source, "artifact_type": node_type},
            )
        created_ids.append(node.id)
    return created_ids


def mark_task(db: Session, task_id: str, status: str, error: str | None = None, result: dict[str, Any] | None = None) -> None:
    record = db.get(TaskRecord, task_id)
    if not record:
        return
    record.status = status
    if status == "running":
        record.started_at = datetime.utcnow()
    if status in {"completed", "failed"}:
        record.finished_at = datetime.utcnow()
    if error:
        record.error = error
    if result is not None:
        record.result = result


def mark_investigation(db: Session, investigation_id: str, status: str) -> None:
    investigation = db.get(Investigation, investigation_id)
    if investigation:
        investigation.status = status
        investigation.updated_at = datetime.utcnow()


def make_task_emitter(task_id: str, investigation_id: str):
    async def _emit(message: str, payload: dict[str, Any] | None = None) -> None:
        emit(task_id, "tool", message, payload or {}, investigation_id)

    return _emit


class RedisLineWriter(io.TextIOBase):
    def __init__(self, task_id: str, investigation_id: str, level: str = "tool"):
        self.task_id = task_id
        self.investigation_id = investigation_id
        self.level = level
        self.buffer = ""

    def writable(self) -> bool:
        return True

    def write(self, chunk: str) -> int:
        if not chunk:
            return 0
        self.buffer += chunk
        while "\n" in self.buffer:
            line, self.buffer = self.buffer.split("\n", 1)
            if line.strip():
                emit(self.task_id, self.level, line, investigation_id=self.investigation_id)
        return len(chunk)

    def flush(self) -> None:
        if self.buffer.strip():
            emit(self.task_id, self.level, self.buffer, investigation_id=self.investigation_id)
        self.buffer = ""


def platform_icon(hostname: str) -> str:
    host = hostname.lower()
    if "github" in host:
        return "github"
    if "gitlab" in host:
        return "gitlab"
    if "twitter" in host or "x.com" in host:
        return "x"
    if "instagram" in host:
        return "instagram"
    if "facebook" in host:
        return "facebook"
    if "linkedin" in host:
        return "linkedin"
    if "reddit" in host:
        return "reddit"
    if "tiktok" in host:
        return "tiktok"
    if "youtube" in host:
        return "youtube"
    return "globe"


def normalize_nexus_result(raw: Any) -> list[dict[str, Any]]:
    def object_to_dict(value: Any) -> Any:
        if is_dataclass(value):
            return asdict(value)
        if isinstance(value, dict):
            return value
        if hasattr(value, "__dict__"):
            return {key: item for key, item in vars(value).items() if not key.startswith("_")}
        return value

    payload = object_to_dict(raw)
    if isinstance(payload, dict) and "results" in payload and isinstance(payload["results"], list):
        items = payload["results"]
    elif isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        items = [payload]
    else:
        items = []

    normalized: list[dict[str, Any]] = []
    for raw_item in items:
        item = object_to_dict(raw_item)
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or item.get("state") or "").lower()
        found = bool(item.get("found")) or status in {"found", "exists", "active", "success", "200"}
        url = item.get("url") or item.get("profile_url") or item.get("link") or item.get("site_url") or ""
        site = item.get("site") or item.get("platform") or item.get("name") or (url.split("/")[2] if "://" in url else "unknown")
        if found or url:
            normalized.append(
                {
                    "site": str(site),
                    "url": str(url or site),
                    "found": found,
                    "status": status or "observed",
                    "raw": item,
                }
            )
    return normalized


async def run_legacy_nexus(username: str, mode: str) -> Any:
    try:
        from nexusrecon.main import NexusRecon
    except ModuleNotFoundError:
        module_path = os.path.join(os.getcwd(), "nexusrecon", "main.py")
        spec = importlib.util.spec_from_file_location("nexusrecon.main", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Unable to load NexusRecon from {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules.setdefault("nexusrecon.main", module)
        spec.loader.exec_module(module)
        NexusRecon = module.NexusRecon

    recon = NexusRecon()
    if hasattr(recon, "scan_username"):
        result = recon.scan_username(username)
        if asyncio.iscoroutine(result):
            return await result
        return result
    if hasattr(recon, "run"):
        result = recon.run(username)
        if asyncio.iscoroutine(result):
            return await result
        return result
    raise RuntimeError("NexusRecon exposes neither scan_username nor run")


@celery_app.task(bind=True, name="nexusintel.nexusrecon")
def run_nexusrecon_task(
    self,
    task_id: str,
    investigation_id: str,
    target: str,
    mode: str = "standard",
    parent_node_id: str | None = None,
) -> dict[str, Any]:
    db = task_session()
    try:
        mark_task(db, task_id, "running")
        mark_investigation(db, investigation_id, "running")
        db.commit()
        username = normalize_username(target)
        if not username:
            raise ValueError("Username target is empty after normalization")
        emit(
            task_id,
            "info",
            f"Starting standalone NexusRecon username sweep: {username}",
            {"mode": mode, "raw_target": target, "normalized_username": username},
            investigation_id,
        )

        parent = db.get(Entity, parent_node_id) if parent_node_id else None
        if not parent:
            parent = upsert_entity(
                db,
                investigation_id,
                type_="username",
                label=username,
                value=username,
                source="nexusrecon",
                confidence="confirmed",
                data={"role": "pivot", "mode": mode, "raw_input": target},
            )
            db.commit()

        identity_analysis = asyncio.run(analyze_identity_target(username, mode))
        identity_nodes = persist_artifacts(db, investigation_id, parent, identity_analysis["artifacts"], "identity_recon")
        db.commit()
        emit(
            task_id,
            "tool",
            f"Identity parser normalized {len(identity_nodes)} public-source pivots for {username}",
            {"kind": identity_analysis["kind"], "target": identity_analysis["target"], "guardrails": identity_analysis["guardrails"]},
            investigation_id,
        )

        identity_limit = None if mode in {"standard", "aggressive"} else 48
        ghost_identity = asyncio.run(IdentityResolver(concurrency=72, timeout=10).resolve(username, emit=make_task_emitter(task_id, investigation_id), limit=identity_limit))
        ghost_identity_nodes = persist_artifacts(db, investigation_id, parent, ghost_identity["artifacts"], "ghost_identity")
        db.commit()
        emit(
            task_id,
            "tool",
            f"Ghost identity engine checked {ghost_identity['checked']} platforms and normalized {len(ghost_identity_nodes)} live public signals",
            {"checked": ghost_identity["checked"], "found": ghost_identity["found"]},
            investigation_id,
        )

        writer = RedisLineWriter(task_id, investigation_id)
        with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
            raw = asyncio.run(run_legacy_nexus(username, mode))
        writer.flush()

        results = normalize_nexus_result(raw)
        found_count = 0
        for item in results:
            if not item.get("found") and mode != "aggressive":
                continue
            platform = item["site"]
            profile = item["url"]
            platform_node = upsert_entity(
                db,
                investigation_id,
                type_="platform",
                label=platform,
                value=platform.lower(),
                source="nexusrecon",
                confidence="medium",
                data={"icon": platform_icon(platform), "category": "username_presence"},
            )
            profile_node = upsert_entity(
                db,
                investigation_id,
                type_="profile",
                label=f"{username} @ {platform}",
                value=profile,
                source="nexusrecon",
                confidence="high" if item.get("found") else "low",
                data={"platform": platform, "url": profile, "status": item.get("status"), "raw": item.get("raw", {})},
            )
            upsert_relationship(
                db,
                investigation_id,
                source_id=parent.id,
                target_id=profile_node.id,
                type_="registered_on" if item.get("found") else "observed_on",
                source="nexusrecon",
                confidence="high" if item.get("found") else "low",
            )
            upsert_relationship(
                db,
                investigation_id,
                source_id=profile_node.id,
                target_id=platform_node.id,
                type_="hosted_by",
                source="nexusrecon",
                confidence="medium",
            )
            profile_host = domain_from_target(profile)
            if profile_host and "." in profile_host:
                host_node = upsert_entity(
                    db,
                    investigation_id,
                    type_="domain",
                    label=profile_host,
                    value=profile_host,
                    source="cascade_correlation",
                    confidence="medium",
                    data={"stage": "profile_host_extraction", "profile_url": profile},
                )
                upsert_relationship(
                    db,
                    investigation_id,
                    source_id=profile_node.id,
                    target_id=host_node.id,
                    type_="HOSTED_BY_DOMAIN",
                    source="cascade_correlation",
                    confidence="medium",
                )
            found_count += 1

        result = {
            "target": username,
            "raw_target": target,
            "mode": mode,
            "profiles": found_count,
            "raw_count": len(results),
            "identity_artifacts": len(identity_nodes),
            "ghost_identity_artifacts": len(ghost_identity_nodes) if "ghost_identity_nodes" in locals() else 0,
        }
        mark_task(db, task_id, "completed", result=result)
        mark_investigation(db, investigation_id, "completed")
        db.commit()
        level = "success" if found_count else "warning"
        message = f"NexusRecon sweep completed: {found_count} confirmed profile signals normalized"
        if not found_count:
            message += "; no confirmed public profiles matched this handle"
        emit(task_id, level, message, result, investigation_id)
        return result
    except Exception as exc:
        db.rollback()
        mark_task(db, task_id, "failed", error=str(exc), result={"target": target})
        mark_investigation(db, investigation_id, "failed")
        db.commit()
        emit(task_id, "error", f"NexusRecon task failed: {exc}", {"target": target}, investigation_id)
        raise
    finally:
        db.close()


def split_email(value: str) -> tuple[str, str]:
    email = value.strip().lower()
    if "@" not in email:
        domain = email.replace("https://", "").replace("http://", "").split("/")[0].split(":")[0].strip(".")
        return "", domain
    local, domain = email.rsplit("@", 1)
    return local, domain


def resolve_records(domain: str, record_type: str) -> list[str]:
    try:
        answers = dns.resolver.resolve(domain, record_type, lifetime=6)
        values = []
        for answer in answers:
            if record_type in {"MX"}:
                values.append(str(answer.exchange).rstrip("."))
            elif record_type in {"TXT", "SPF"}:
                chunks = getattr(answer, "strings", None)
                if chunks:
                    values.append("".join(part.decode("utf-8", "ignore") for part in chunks))
                else:
                    values.append(str(answer).strip('"'))
            else:
                values.append(str(answer).rstrip("."))
        return sorted(set(values))
    except Exception:
        return []


async def fetch_gravatar(email: str) -> dict[str, Any]:
    digest = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    url = f"https://www.gravatar.com/avatar/{digest}?d=404"
    async with httpx.AsyncClient(timeout=8, follow_redirects=False) as client:
        try:
            response = await client.get(url)
            return {"hash": digest, "exists": response.status_code == 200, "status_code": response.status_code, "url": url}
        except httpx.HTTPError as exc:
            return {"hash": digest, "exists": False, "error": str(exc), "url": url}


def infer_workspace(mx_records: list[str], txt_records: list[str], domain: str) -> list[dict[str, Any]]:
    joined_mx = " ".join(mx_records).lower()
    joined_txt = " ".join(txt_records).lower()
    services: list[dict[str, Any]] = []
    if "google.com" in joined_mx or "googlemail.com" in joined_mx or domain in {"gmail.com", "googlemail.com"}:
        services.append({"name": "Google Workspace / Google Account", "kind": "workspace", "icon": "google", "confidence": "high"})
    if "outlook.com" in joined_mx or "protection.outlook.com" in joined_mx or "hotmail.com" in domain:
        services.append({"name": "Microsoft 365 / Outlook", "kind": "workspace", "icon": "microsoft", "confidence": "high"})
    if "zoho" in joined_mx:
        services.append({"name": "Zoho Mail", "kind": "workspace", "icon": "mail", "confidence": "medium"})
    if "protonmail" in joined_mx or domain in {"proton.me", "protonmail.com"}:
        services.append({"name": "Proton Mail", "kind": "workspace", "icon": "shield", "confidence": "high"})
    if "spf1" in joined_txt:
        services.append({"name": "SPF Policy", "kind": "email_security", "icon": "shield-check", "confidence": "medium"})
    if "_dmarc" in joined_txt or any("dmarc" in record for record in txt_records):
        services.append({"name": "DMARC Policy", "kind": "email_security", "icon": "shield-check", "confidence": "medium"})
    return services


@celery_app.task(bind=True, name="nexusintel.email_google")
def run_email_google_task(
    self,
    task_id: str,
    investigation_id: str,
    target: str,
    mode: str = "standard",
    parent_node_id: str | None = None,
    transform: str = "email_footprint",
) -> dict[str, Any]:
    db = task_session()
    try:
        mark_task(db, task_id, "running")
        mark_investigation(db, investigation_id, "running")
        db.commit()
        local, domain = split_email(target)
        emit(task_id, "info", f"Starting email/workspace recon for {target}", {"mode": mode, "transform": transform}, investigation_id)

        parent = db.get(Entity, parent_node_id) if parent_node_id else None
        if not parent:
            parent = upsert_entity(
                db,
                investigation_id,
                type_="email" if "@" in target else "domain",
                label=target,
                value=target,
                source="email_recon",
                confidence="confirmed",
                data={"role": "pivot"},
            )

        ghost_email = asyncio.run(EmailPresenceResolver(timeout=10, identity_limit=24 if mode == "passive" else 64).resolve(target, emit=make_task_emitter(task_id, investigation_id)))
        ghost_email_nodes = persist_artifacts(db, investigation_id, parent, ghost_email["artifacts"], "ghost_email")
        db.commit()
        emit(
            task_id,
            "tool",
            f"Ghost email engine normalized {len(ghost_email_nodes)} public posture signals",
            {"domain": ghost_email.get("domain"), "valid": ghost_email.get("valid")},
            investigation_id,
        )

        email_analysis = asyncio.run(analyze_email_target(target, mode))
        validator_nodes = persist_artifacts(db, investigation_id, parent, email_analysis["artifacts"], "email_recon")
        db.commit()
        emit(
            task_id,
            "tool",
            f"Deep email parser produced {len(validator_nodes)} normalized graph artifacts",
            {
                "valid": email_analysis["valid"],
                "has_mx": email_analysis["has_mx"],
                "disposable": email_analysis["disposable"],
            },
            investigation_id,
        )

        if "@" in target:
            username_node = upsert_entity(
                db,
                investigation_id,
                type_="username",
                label=local,
                value=local,
                source="email_recon",
                confidence="medium",
                data={"derived_from": target},
            )
            upsert_relationship(
                db,
                investigation_id,
                source_id=parent.id,
                target_id=username_node.id,
                type_="has_local_part",
                source="email_recon",
                confidence="medium",
            )

        domain_node = upsert_entity(
            db,
            investigation_id,
            type_="domain",
            label=domain,
            value=domain,
            source="email_recon",
            confidence="high",
            data={"role": "mail_domain"},
        )
        upsert_relationship(
            db,
            investigation_id,
            source_id=parent.id,
            target_id=domain_node.id,
            type_="uses_domain",
            source="email_recon",
            confidence="high",
        )

        mx = resolve_records(domain, "MX")
        txt = resolve_records(domain, "TXT")
        dmarc = resolve_records(f"_dmarc.{domain}", "TXT")
        bimi = resolve_records(f"default._bimi.{domain}", "TXT")
        emit(task_id, "tool", f"DNS MX={len(mx)} TXT={len(txt)} DMARC={len(dmarc)} BIMI={len(bimi)}", investigation_id=investigation_id)

        for record_type, values in {"MX": mx, "TXT": txt, "DMARC": dmarc, "BIMI": bimi}.items():
            for value in values[:30]:
                record_node = upsert_entity(
                    db,
                    investigation_id,
                    type_="dns_record",
                    label=f"{record_type} {value[:80]}",
                    value=f"{record_type}:{domain}:{value}",
                    source="dns",
                    confidence="high",
                    data={"record_type": record_type, "record": value},
                )
                upsert_relationship(
                    db,
                    investigation_id,
                    source_id=domain_node.id,
                    target_id=record_node.id,
                    type_="has_dns_record",
                    source="dns",
                    confidence="high",
                )

        services = infer_workspace(mx, txt + dmarc, domain)
        for service in services:
            service_node = upsert_entity(
                db,
                investigation_id,
                type_="service",
                label=service["name"],
                value=f"{domain}:{service['name']}",
                source="workspace_recon",
                confidence=service["confidence"],
                data=service,
            )
            upsert_relationship(
                db,
                investigation_id,
                source_id=domain_node.id,
                target_id=service_node.id,
                type_="uses_service",
                source="workspace_recon",
                confidence=service["confidence"],
            )

        gravatar = asyncio.run(fetch_gravatar(target)) if "@" in target and mode in {"standard", "aggressive"} else None
        if gravatar:
            gravatar_node = upsert_entity(
                db,
                investigation_id,
                type_="avatar_hash",
                label="Gravatar MD5",
                value=gravatar["hash"],
                source="public_avatar",
                confidence="high" if gravatar.get("exists") else "low",
                data=gravatar,
            )
            upsert_relationship(
                db,
                investigation_id,
                source_id=parent.id,
                target_id=gravatar_node.id,
                type_="has_public_avatar_hash",
                source="public_avatar",
                confidence="high" if gravatar.get("exists") else "low",
            )
            emit(
                task_id,
                "tool",
                f"Public avatar hash checked: status={gravatar.get('status_code')} exists={gravatar.get('exists')}",
                gravatar,
                investigation_id,
            )

        result = {
            "target": target,
            "domain": domain,
            "mx": len(mx),
            "txt": len(txt),
            "services": len(services),
            "gravatar": gravatar,
            "validator_artifacts": len(validator_nodes),
            "ghost_email_artifacts": len(ghost_email_nodes) if "ghost_email_nodes" in locals() else 0,
            "guardrails": email_analysis["guardrails"],
        }
        mark_task(db, task_id, "completed", result=result)
        mark_investigation(db, investigation_id, "completed")
        db.commit()
        emit(task_id, "success", f"Email/workspace recon completed for {target}", result, investigation_id)
        return result
    except Exception as exc:
        db.rollback()
        mark_task(db, task_id, "failed", error=str(exc), result={"target": target})
        mark_investigation(db, investigation_id, "failed")
        db.commit()
        emit(task_id, "error", f"Email/workspace task failed: {exc}", {"target": target}, investigation_id)
        raise
    finally:
        db.close()


def domain_from_target(target: str) -> str:
    value = target.strip().lower().replace("https://", "").replace("http://", "")
    return value.split("/")[0].split(":")[0]


@celery_app.task(bind=True, name="nexusintel.domain")
def run_domain_task(
    self,
    task_id: str,
    investigation_id: str,
    target: str,
    mode: str = "standard",
    parent_node_id: str | None = None,
    transform: str = "domain_recon",
) -> dict[str, Any]:
    db = task_session()
    try:
        mark_task(db, task_id, "running")
        mark_investigation(db, investigation_id, "running")
        db.commit()
        domain = domain_from_target(target)
        emit(task_id, "info", f"Starting domain recon for {domain}", {"mode": mode, "transform": transform}, investigation_id)

        parent = db.get(Entity, parent_node_id) if parent_node_id else None
        if not parent:
            parent = upsert_entity(
                db,
                investigation_id,
                type_="domain",
                label=domain,
                value=domain,
                source="domain_recon",
                confidence="confirmed",
            )

        network_analysis = asyncio.run(analyze_network_target(target, mode))
        validator_nodes = persist_artifacts(db, investigation_id, parent, network_analysis["artifacts"], "network_recon")
        db.commit()
        emit(
            task_id,
            "tool",
            f"Network parser produced {len(validator_nodes)} normalized graph artifacts",
            {"kind": network_analysis["kind"], "target": network_analysis["target"]},
            investigation_id,
        )

        record_sets = {
            "A": resolve_records(domain, "A"),
            "AAAA": resolve_records(domain, "AAAA"),
            "MX": resolve_records(domain, "MX"),
            "NS": resolve_records(domain, "NS"),
            "TXT": resolve_records(domain, "TXT"),
            "CAA": resolve_records(domain, "CAA"),
        }
        ip_count = 0
        for record_type, values in record_sets.items():
            for value in values[:40]:
                node_type = "ip" if record_type in {"A", "AAAA"} else "dns_record"
                label = value if node_type == "ip" else f"{record_type} {value[:90]}"
                node = upsert_entity(
                    db,
                    investigation_id,
                    type_=node_type,
                    label=label,
                    value=value if node_type == "ip" else f"{record_type}:{domain}:{value}",
                    source="dns",
                    confidence="high",
                    data={"record_type": record_type, "record": value},
                )
                upsert_relationship(
                    db,
                    investigation_id,
                    source_id=parent.id,
                    target_id=node.id,
                    type_="resolves_to" if node_type == "ip" else "has_dns_record",
                    source="dns",
                    confidence="high",
                )
                if node_type == "ip":
                    ip_count += 1

        if mode in {"standard", "aggressive"}:
            for subdomain in [f"www.{domain}", f"mail.{domain}", f"api.{domain}", f"dev.{domain}"]:
                try:
                    socket.gethostbyname(subdomain)
                    sub_node = upsert_entity(
                        db,
                        investigation_id,
                        type_="domain",
                        label=subdomain,
                        value=subdomain,
                        source="subdomain_probe",
                        confidence="medium",
                        data={"method": "dns_resolution_candidate"},
                    )
                    upsert_relationship(
                        db,
                        investigation_id,
                        source_id=parent.id,
                        target_id=sub_node.id,
                        type_="has_subdomain",
                        source="subdomain_probe",
                        confidence="medium",
                    )
                    emit(task_id, "tool", f"Resolved candidate subdomain: {subdomain}", investigation_id=investigation_id)
                except OSError:
                    continue

        result = {
            "domain": domain,
            "records": {key: len(value) for key, value in record_sets.items()},
            "ips": ip_count,
            "validator_artifacts": len(validator_nodes),
            "network_kind": network_analysis["kind"],
            "rdap": network_analysis.get("rdap"),
            "subdomains": len(network_analysis.get("subdomains", [])),
        }
        mark_task(db, task_id, "completed", result=result)
        mark_investigation(db, investigation_id, "completed")
        db.commit()
        emit(task_id, "success", f"Domain recon completed for {domain}", result, investigation_id)
        return result
    except Exception as exc:
        db.rollback()
        mark_task(db, task_id, "failed", error=str(exc), result={"target": target})
        mark_investigation(db, investigation_id, "failed")
        db.commit()
        emit(task_id, "error", f"Domain recon failed: {exc}", {"target": target}, investigation_id)
        raise
    finally:
        db.close()


@celery_app.task(bind=True, name="nexusintel.phone")
def run_phone_task(
    self,
    task_id: str,
    investigation_id: str,
    target: str,
    mode: str = "standard",
    parent_node_id: str | None = None,
    transform: str = "phone_recon",
) -> dict[str, Any]:
    db = task_session()
    try:
        mark_task(db, task_id, "running")
        mark_investigation(db, investigation_id, "running")
        db.commit()
        emit(task_id, "info", f"Starting public numbering-plan recon for {target}", {"mode": mode, "transform": transform}, investigation_id)

        parent = db.get(Entity, parent_node_id) if parent_node_id else None
        analysis = analyze_phone_target(target, mode)
        if not parent:
            parent = upsert_entity(
                db,
                investigation_id,
                type_="phone",
                label=analysis["target"] or target,
                value=analysis["target"] or target,
                source="phone_recon",
                confidence="high" if analysis["valid_e164"] else "low",
                data={"role": "pivot", "valid_e164": analysis["valid_e164"]},
            )

        ghost_phone = asyncio.run(PhoneResolver().resolve(target, emit=make_task_emitter(task_id, investigation_id)))
        ghost_phone_nodes = persist_artifacts(db, investigation_id, parent, ghost_phone["artifacts"], "ghost_phone")
        db.commit()
        emit(
            task_id,
            "tool",
            f"Ghost phone engine normalized {len(ghost_phone_nodes)} public numbering-plan signals",
            {"valid_e164": ghost_phone.get("valid_e164"), "plan": ghost_phone.get("plan", {})},
            investigation_id,
        )

        validator_nodes = persist_artifacts(db, investigation_id, parent, analysis["artifacts"], "phone_recon")
        result = {
            "target": analysis["target"],
            "valid_e164": analysis["valid_e164"],
            "calling_code": analysis["calling_code"],
            "line_type": analysis["line_type"],
            "validator_artifacts": len(validator_nodes),
            "ghost_phone_artifacts": len(ghost_phone_nodes) if "ghost_phone_nodes" in locals() else 0,
            "guardrails": analysis["guardrails"],
        }
        mark_task(db, task_id, "completed", result=result)
        mark_investigation(db, investigation_id, "completed")
        db.commit()
        emit(task_id, "success", f"Phone recon completed for {analysis['target']}", result, investigation_id)
        return result
    except Exception as exc:
        db.rollback()
        mark_task(db, task_id, "failed", error=str(exc), result={"target": target})
        mark_investigation(db, investigation_id, "failed")
        db.commit()
        emit(task_id, "error", f"Phone recon failed: {exc}", {"target": target}, investigation_id)
        raise
    finally:
        db.close()

def macro_target_type(value: str) -> str:
    target = value.strip()
    if "@" in target and "." in target.rsplit("@", 1)[-1]:
        return "email"
    if target.replace("+", "").replace("-", "").replace(" ", "").isdigit() and len(target) >= 7:
        return "phone"
    try:
        socket.inet_aton(target)
        return "ip"
    except OSError:
        pass
    if "." in target and " " not in target:
        return "domain"
    return "username"


@celery_app.task(bind=True, name="nexusintel.full_identity_pipeline")
def run_full_identity_pipeline_task(
    self,
    task_id: str,
    investigation_id: str,
    target: str,
    mode: str = "standard",
    parent_node_id: str | None = None,
    transform: str = "full_identity_pipeline",
) -> dict[str, Any]:
    db = task_session()
    try:
        mark_task(db, task_id, "running")
        mark_investigation(db, investigation_id, "running")
        db.commit()

        kind = macro_target_type(target)
        emit(
            task_id,
            "info",
            f"Starting autonomous identity macro for {target}",
            {"mode": mode, "transform": transform, "kind": kind},
            investigation_id,
        )

        parent = db.get(Entity, parent_node_id) if parent_node_id else None
        if not parent:
            parent = upsert_entity(
                db,
                investigation_id,
                type_=kind,
                label=target,
                value=target,
                source="macro_pipeline",
                confidence="confirmed",
                data={"role": "macro_root", "mode": mode},
            )
            db.commit()

        created_total = 0
        profile_total = 0
        domains: set[str] = set()

        if kind == "email":
            local, domain = split_email(target)
            domains.add(domain)
            email_analysis = asyncio.run(analyze_email_target(target, mode))
            created = persist_artifacts(db, investigation_id, parent, email_analysis["artifacts"], "macro_email_recon")
            created_total += len(created)
            emit(
                task_id,
                "tool",
                f"Macro email stage normalized {len(created)} artifacts; domain={domain}",
                {"valid": email_analysis["valid"], "has_mx": email_analysis["has_mx"], "disposable": email_analysis["disposable"]},
                investigation_id,
            )
            if local:
                username_node = upsert_entity(
                    db,
                    investigation_id,
                    type_="username",
                    label=local,
                    value=local,
                    source="macro_email_recon",
                    confidence="medium",
                    data={"derived_from": target, "stage": "local_part"},
                )
                upsert_relationship(
                    db,
                    investigation_id,
                    source_id=parent.id,
                    target_id=username_node.id,
                    type_="HAS_LOCAL_PART",
                    source="macro_email_recon",
                    confidence="medium",
                )

        elif kind == "username":
            username = normalize_username(target)
            identity_analysis = asyncio.run(analyze_identity_target(username, mode))
            created = persist_artifacts(db, investigation_id, parent, identity_analysis["artifacts"], "macro_identity_recon")
            created_total += len(created)
            emit(task_id, "tool", f"Macro identity stage normalized {len(created)} passive pivots", identity_analysis.get("guardrails", {}), investigation_id)

            writer = RedisLineWriter(task_id, investigation_id)
            with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
                raw = asyncio.run(run_legacy_nexus(username, mode))
            writer.flush()
            for item in normalize_nexus_result(raw):
                if not item.get("found") and mode != "aggressive":
                    continue
                platform = item["site"]
                profile = item["url"]
                platform_node = upsert_entity(
                    db,
                    investigation_id,
                    type_="platform",
                    label=platform,
                    value=platform.lower(),
                    source="macro_nexusrecon",
                    confidence="medium",
                    data={"icon": platform_icon(platform), "stage": "macro_profile_sweep"},
                )
                profile_node = upsert_entity(
                    db,
                    investigation_id,
                    type_="profile",
                    label=f"{username} @ {platform}",
                    value=profile,
                    source="macro_nexusrecon",
                    confidence="high" if item.get("found") else "low",
                    data={"platform": platform, "url": profile, "status": item.get("status"), "raw": item.get("raw", {})},
                )
                upsert_relationship(
                    db,
                    investigation_id,
                    source_id=parent.id,
                    target_id=profile_node.id,
                    type_="REGISTERED_ON" if item.get("found") else "OBSERVED_ON",
                    source="macro_nexusrecon",
                    confidence="high" if item.get("found") else "low",
                )
                upsert_relationship(
                    db,
                    investigation_id,
                    source_id=profile_node.id,
                    target_id=platform_node.id,
                    type_="HOSTED_BY",
                    source="macro_nexusrecon",
                    confidence="medium",
                )
                profile_host = domain_from_target(profile)
                if profile_host and "." in profile_host:
                    host_node = upsert_entity(
                        db,
                        investigation_id,
                        type_="domain",
                        label=profile_host,
                        value=profile_host,
                        source="macro_cascade",
                        confidence="medium",
                        data={"stage": "profile_host_extraction", "profile_url": profile},
                    )
                    upsert_relationship(
                        db,
                        investigation_id,
                        source_id=profile_node.id,
                        target_id=host_node.id,
                        type_="HOSTED_BY_DOMAIN",
                        source="macro_cascade",
                        confidence="medium",
                    )
                profile_total += 1

        elif kind == "phone":
            analysis = analyze_phone_target(target, mode)
            created = persist_artifacts(db, investigation_id, parent, analysis["artifacts"], "macro_phone_recon")
            created_total += len(created)
            emit(task_id, "tool", f"Macro phone stage normalized {len(created)} numbering-plan pivots", analysis.get("guardrails", {}), investigation_id)

        else:
            domains.add(domain_from_target(target))

        for domain in sorted(domain for domain in domains if domain):
            domain_node = upsert_entity(
                db,
                investigation_id,
                type_="domain",
                label=domain,
                value=domain,
                source="macro_network_recon",
                confidence="high",
                data={"role": "macro_domain", "stage": "domain_extraction"},
            )
            upsert_relationship(
                db,
                investigation_id,
                source_id=parent.id,
                target_id=domain_node.id,
                type_="USES_DOMAIN",
                source="macro_network_recon",
                confidence="high",
            )
            network_analysis = asyncio.run(analyze_network_target(domain, mode))
            created = persist_artifacts(db, investigation_id, domain_node, network_analysis["artifacts"], "macro_network_recon")
            created_total += len(created)
            emit(task_id, "tool", f"Macro network stage normalized {len(created)} public DNS/RDAP pivots for {domain}", {"kind": network_analysis["kind"]}, investigation_id)

            record_sets = {"A": resolve_records(domain, "A"), "AAAA": resolve_records(domain, "AAAA"), "MX": resolve_records(domain, "MX")}
            for record_type, values in record_sets.items():
                for value in values[:24]:
                    node_type = "ip" if record_type in {"A", "AAAA"} else "dns_record"
                    node = upsert_entity(
                        db,
                        investigation_id,
                        type_=node_type,
                        label=value if node_type == "ip" else f"{record_type} {value[:90]}",
                        value=value if node_type == "ip" else f"{record_type}:{domain}:{value}",
                        source="macro_dns",
                        confidence="high",
                        data={"record_type": record_type, "record": value, "stage": "macro_dns_resolution"},
                    )
                    upsert_relationship(
                        db,
                        investigation_id,
                        source_id=domain_node.id,
                        target_id=node.id,
                        type_="RESOLVES_TO" if node_type == "ip" else "HAS_MX_RECORD",
                        source="macro_dns",
                        confidence="high",
                    )

        result = {
            "target": target,
            "kind": kind,
            "mode": mode,
            "created_artifacts": created_total,
            "profiles": profile_total,
            "domains": sorted(domains),
        }
        mark_task(db, task_id, "completed", result=result)
        mark_investigation(db, investigation_id, "completed")
        db.commit()
        emit(task_id, "success", f"Autonomous identity macro completed: {created_total} artifacts, {profile_total} profiles", result, investigation_id)
        return result
    except Exception as exc:
        db.rollback()
        mark_task(db, task_id, "failed", error=str(exc), result={"target": target, "transform": transform})
        mark_investigation(db, investigation_id, "failed")
        db.commit()
        emit(task_id, "error", f"Autonomous identity macro failed: {exc}", {"target": target, "transform": transform}, investigation_id)
        raise
    finally:
        db.close()
