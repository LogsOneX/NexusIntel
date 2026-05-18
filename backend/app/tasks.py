from datetime import datetime, timezone

from sqlalchemy import select

from app.celery_app import celery
from app.database import init_db, session_scope
from app.events import emit_event
from app.graph_store import persist_batch, refresh_summary
from app.models import Investigation
from app.osint.runner import OSINTRunner
from workers.legacy_nexus import LegacyNexusReconBridge


@celery.task(name="app.tasks.run_investigation")
def run_investigation(investigation_id: str) -> None:
    import asyncio

    init_db()
    asyncio.run(_run_investigation(investigation_id))


@celery.task(name="app.tasks.expand_entity")
def expand_entity(investigation_id: str, entity_id: str, mode: str) -> None:
    import asyncio

    init_db()
    asyncio.run(_expand_entity(investigation_id, entity_id, mode))


@celery.task(name="app.tasks.run_legacy_nexusrecon")
def run_legacy_nexusrecon(investigation_id: str, target: str, mode: str) -> None:
    import asyncio

    init_db()
    asyncio.run(_run_legacy_nexusrecon(investigation_id, target, mode))


async def _run_investigation(investigation_id: str) -> None:
    runner = OSINTRunner()
    with session_scope() as session:
        investigation = session.scalar(select(Investigation).where(Investigation.id == investigation_id))
        if not investigation:
            return
        investigation.status = "running"
        investigation.updated_at = datetime.now(timezone.utc)
        session.commit()
        try:
            await runner.run_initial(session, investigation)
            investigation.status = "completed"
            investigation.completed_at = datetime.now(timezone.utc)
            investigation.updated_at = datetime.now(timezone.utc)
            session.commit()
            emit_event(investigation.id, "success", "Investigation completed.", "engine", investigation.summary)
        except Exception as exc:
            session.rollback()
            investigation = session.scalar(select(Investigation).where(Investigation.id == investigation_id))
            if investigation:
                investigation.status = "failed"
                investigation.error = str(exc)
                investigation.updated_at = datetime.now(timezone.utc)
                session.commit()
            emit_event(investigation_id, "error", f"Investigation failed: {exc}", "engine")


async def _expand_entity(investigation_id: str, entity_id: str, mode: str) -> None:
    runner = OSINTRunner()
    with session_scope() as session:
        investigation = session.scalar(select(Investigation).where(Investigation.id == investigation_id))
        if not investigation:
            return
        previous_status = investigation.status
        investigation.status = "expanding"
        investigation.updated_at = datetime.now(timezone.utc)
        session.commit()
        try:
            await runner.run_expansion(session, investigation, entity_id, mode or investigation.mode)
            investigation.status = "completed" if previous_status in {"completed", "failed"} else previous_status
            investigation.updated_at = datetime.now(timezone.utc)
            session.commit()
            emit_event(investigation.id, "success", "Entity expansion completed.", "engine", {"entity_id": entity_id})
        except Exception as exc:
            session.rollback()
            investigation = session.scalar(select(Investigation).where(Investigation.id == investigation_id))
            if investigation:
                investigation.status = "failed"
                investigation.error = str(exc)
                investigation.updated_at = datetime.now(timezone.utc)
                session.commit()
            emit_event(investigation_id, "error", f"Expansion failed: {exc}", "engine")


async def _run_legacy_nexusrecon(investigation_id: str, target: str, mode: str) -> None:
    bridge = LegacyNexusReconBridge()
    with session_scope() as session:
        investigation = session.scalar(select(Investigation).where(Investigation.id == investigation_id))
        if not investigation:
            return
        previous_status = investigation.status
        investigation.status = "legacy-running"
        investigation.updated_at = datetime.now(timezone.utc)
        session.commit()
        try:
            batch = await bridge.run(target or investigation.target, investigation.target_type, mode or investigation.mode, investigation.id)
            stats = persist_batch(session, investigation.id, batch.to_dict())
            refresh_summary(session, investigation)
            investigation.status = "completed" if previous_status in {"completed", "failed"} else previous_status
            investigation.updated_at = datetime.now(timezone.utc)
            session.commit()
            emit_event(
                investigation.id,
                "success",
                "Legacy NexusRecon bridge completed.",
                bridge.name,
                {"entities": stats["entities"], "relationships": stats["relationships"]},
            )
        except Exception as exc:
            session.rollback()
            investigation = session.scalar(select(Investigation).where(Investigation.id == investigation_id))
            if investigation:
                investigation.status = "failed"
                investigation.error = str(exc)
                investigation.updated_at = datetime.now(timezone.utc)
                session.commit()
            emit_event(investigation_id, "error", f"Legacy NexusRecon bridge failed: {exc}", bridge.name)
