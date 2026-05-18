from __future__ import annotations

import asyncio
import contextlib
import hashlib
import io
import json
import os
import socket
import sys
import uuid
from datetime import datetime
from typing import Any

import dns.resolver
import httpx
import redis
from celery import Celery
from sqlalchemy import Column, DateTime, ForeignKey, String, Text, UniqueConstraint, create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session, declarative_base, sessionmaker


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
    db.flush()
    return edge


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
    if isinstance(raw, dict) and "results" in raw and isinstance(raw["results"], list):
        items = raw["results"]
    elif isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = [raw]
    else:
        items = []

    normalized: list[dict[str, Any]] = []
    for item in items:
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
    from nexusrecon.main import NexusRecon

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
        emit(task_id, "info", f"Starting standalone NexusRecon username sweep: {target}", {"mode": mode}, investigation_id)

        parent = db.get(Entity, parent_node_id) if parent_node_id else None
        if not parent:
            parent = upsert_entity(
                db,
                investigation_id,
                type_="username",
                label=target,
                value=target,
                source="nexusrecon",
                confidence="confirmed",
                data={"role": "pivot", "mode": mode},
            )
            db.commit()

        writer = RedisLineWriter(task_id, investigation_id)
        with contextlib.redirect_stdout(writer), contextlib.redirect_stderr(writer):
            raw = asyncio.run(run_legacy_nexus(target, mode))
        writer.flush()

        results = normalize_nexus_result(raw)
        found_count = 0
        for item in results:
            if not item.get("found") and mode == "passive":
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
                label=f"{target} @ {platform}",
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
            found_count += 1

        result = {"target": target, "mode": mode, "profiles": found_count, "raw_count": len(results)}
        mark_task(db, task_id, "completed", result=result)
        mark_investigation(db, investigation_id, "completed")
        db.commit()
        emit(task_id, "success", f"NexusRecon sweep completed: {found_count} profile signals normalized", result, investigation_id)
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
        return email, email.split(".")[-1] if "." in email else ""
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

        result = {"target": target, "domain": domain, "mx": len(mx), "txt": len(txt), "services": len(services), "gravatar": gravatar}
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

        result = {"domain": domain, "records": {key: len(value) for key, value in record_sets.items()}, "ips": ip_count}
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
