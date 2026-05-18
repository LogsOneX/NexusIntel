from collections.abc import Awaitable, Callable
from typing import Any

from app.events import emit_event
from app.graph_store import persist_batch, refresh_summary, upsert_entity, upsert_relationship
from app.models import Investigation
from app.osint.domain import DomainRecon
from app.osint.email_workspace import EmailWorkspaceRecon
from app.osint.identity import IdentityProfiler
from app.osint.intel_planner import IntelPlanner
from app.osint.phone import PhoneRecon
from app.osint.schema import FindingBatch, entity
from app.osint.website import WebsiteSurfaceRecon
from app.targeting import extract_domain, root_entity_type, username_seed
from workers.legacy_modules import LegacyAnalyticsBridge
from workers.legacy_nexus import LegacyNexusReconBridge


class OSINTRunner:
    def __init__(self) -> None:
        self.planner = IntelPlanner()
        self.identity = IdentityProfiler()
        self.email_workspace = EmailWorkspaceRecon()
        self.domain = DomainRecon()
        self.website = WebsiteSurfaceRecon()
        self.phone = PhoneRecon()
        self.legacy_nexus = LegacyNexusReconBridge()
        self.legacy_modules = LegacyAnalyticsBridge()

    def modules_for(self, target_type: str, mode: str) -> list[Any]:
        modules: list[Any] = [self.planner]
        if target_type in {"username", "email", "url", "unknown"}:
            modules.append(self.identity)
        if target_type in {"email", "domain", "url"}:
            modules.append(self.email_workspace)
        if target_type in {"domain", "url", "email"}:
            modules.append(self.domain)
            modules.append(self.website)
        if target_type == "phone":
            modules.append(self.phone)
        if target_type in {"username", "email", "url", "unknown"}:
            modules.append(self.legacy_nexus)
        modules.append(self.legacy_modules)
        return modules

    async def run_initial(self, session, investigation: Investigation) -> None:
        target_root = entity(root_entity_type(investigation.target_type), investigation.target, investigation.target, 100, "target")
        root = upsert_entity(
            session,
            investigation.id,
            target_root["type"],
            target_root["value"],
            target_root["label"],
            target_root["confidence"],
            "target",
            {"mode": investigation.mode},
        )
        session.commit()

        emit_event(investigation.id, "info", f"Investigation queued for {investigation.target}", "engine")
        for module in self.modules_for(investigation.target_type, investigation.mode):
            await self._run_module(session, investigation, module, investigation.target, investigation.target_type, root)
        refresh_summary(session, investigation)
        session.commit()

    async def run_expansion(self, session, investigation: Investigation, entity_id: str, mode: str) -> None:
        from app.models import Entity

        source = session.get(Entity, entity_id)
        if not source or source.investigation_id != investigation.id:
            emit_event(investigation.id, "error", "Selected entity was not found for expansion.", "engine")
            return

        emit_event(investigation.id, "info", f"Expanding {source.type}: {source.label}", "engine", {"entity_id": entity_id})
        target = source.value
        target_type = self._target_type_for_entity(source.type)
        root = source
        for module in self.modules_for(target_type, mode):
            if isinstance(module, IntelPlanner):
                continue
            await self._run_module(session, investigation, module, target, target_type, root, mode_override=mode)
        refresh_summary(session, investigation)
        session.commit()

    async def _run_module(
        self,
        session,
        investigation: Investigation,
        module: Any,
        target: str,
        target_type: str,
        root,
        mode_override: str | None = None,
    ) -> None:
        emit_event(investigation.id, "info", f"Starting {module.name}", module.name)
        try:
            try:
                batch: FindingBatch = await module.run(target, target_type, mode_override or investigation.mode, investigation.id)
            except TypeError:
                batch = await module.run(target, target_type, mode_override or investigation.mode)
            stats = persist_batch(session, investigation.id, batch.to_dict())
            self._link_batch_to_root(session, investigation.id, root, batch)
            session.commit()
            emit_event(
                investigation.id,
                "success",
                batch.summary,
                module.name,
                {"entities": stats["entities"], "relationships": stats["relationships"]},
            )
        except Exception as exc:
            session.rollback()
            emit_event(investigation.id, "error", f"{module.name} failed: {exc}", module.name)

    def _link_batch_to_root(self, session, investigation_id: str, root, batch: FindingBatch) -> None:
        from app.graph_store import value_key
        from app.models import Entity
        from sqlalchemy import select

        for item in batch.entities[:120]:
            if item["type"] == root.type and value_key(item["value"]) == root.value_key:
                continue
            target = session.scalar(
                select(Entity).where(
                    Entity.investigation_id == investigation_id,
                    Entity.type == item["type"],
                    Entity.value_key == value_key(item["value"]),
                )
            )
            if target:
                upsert_relationship(
                    session,
                    investigation_id,
                    root,
                    target,
                    "observed",
                    "Observed",
                    min(85, max(40, item.get("confidence", 50))),
                    {"module": batch.module},
                )

    def _target_type_for_entity(self, entity_type: str) -> str:
        if entity_type in {"email"}:
            return "email"
        if entity_type in {"domain", "subdomain", "mail_server", "nameserver"}:
            return "domain"
        if entity_type in {"website", "url"}:
            return "url"
        if entity_type == "phone":
            return "phone"
        if entity_type in {"username", "social_profile", "developer_profile", "creator_profile", "identity_profile"}:
            return "username"
        return "unknown"
