from typing import Any

from app.events import emit_event
from app.osint.schema import FindingBatch, entity, relationship
from core.engine import AnalyticsEngine
from core.graph import build_investigation_graph
from core.targets import classify_target


class LegacyAnalyticsBridge:
    name = "legacy_analytics_bridge"

    async def run(
        self,
        target: str,
        target_type: str,
        mode: str,
        investigation_id: str | None = None,
    ) -> FindingBatch:
        if investigation_id:
            emit_event(investigation_id, "info", "Loading legacy core/modules analytics engine.", self.name)

        timeout = 18 if mode == "standard" else 25 if mode == "active" else 35
        concurrency = 5 if mode == "standard" else 8 if mode == "active" else 12
        profile = classify_target(target)
        engine = AnalyticsEngine(module_timeout=timeout, max_concurrent=concurrency, mode=mode)
        engine.load_modules()
        results = await engine.execute_all(target, profile=profile)
        legacy_graph = build_investigation_graph(profile, results)

        entities = []
        relationships = []
        node_refs: dict[str, dict[str, Any]] = {}

        for node in legacy_graph.get("nodes", [])[:420]:
            node_type = _normalize_type(node.get("type", "signal"))
            label = str(node.get("label") or node.get("id") or node_type)
            value = str(node.get("id") or label)
            ref = entity(node_type, value, label, _confidence_from_node(node), self.name, {"legacy_graph": node})
            entities.append(ref)
            node_refs[str(node.get("id") or value)] = ref

        for edge in legacy_graph.get("edges", [])[:800]:
            source = node_refs.get(str(edge.get("source")))
            target_ref = node_refs.get(str(edge.get("target")))
            if source and target_ref:
                rel_type = str(edge.get("relationship") or edge.get("type") or "legacy_link")
                relationships.append(
                    relationship(
                        source,
                        target_ref,
                        _normalize_type(rel_type),
                        rel_type.replace("_", " ").title(),
                        66,
                        {"legacy_edge": edge},
                    )
                )

        module_stats = {
            name: {
                "status": result.get("status"),
                "signals": result.get("signal_count", 0),
                "summary": result.get("summary") or result.get("message"),
            }
            for name, result in results.items()
        }
        entities.append(
            entity(
                "signal",
                f"{target}:legacy-module-summary",
                f"Legacy modules: {len(results)} executed",
                72,
                self.name,
                {"modules": module_stats, "summary": legacy_graph.get("summary", {})},
            )
        )

        return FindingBatch(
            self.name,
            f"Assimilated {len(results)} legacy module result(s) into the unified graph.",
            entities,
            relationships,
            {"modules": module_stats, "legacy_graph_summary": legacy_graph.get("summary", {})},
        )


def _normalize_type(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() else "_" for ch in str(value).lower()).strip("_")
    return cleaned or "signal"


def _confidence_from_node(node: dict[str, Any]) -> int:
    properties = node.get("properties") or {}
    if isinstance(properties, dict):
        for key in ("confidence", "score", "risk_score", "signals"):
            value = properties.get(key)
            if isinstance(value, (int, float)):
                return max(30, min(95, int(value)))
    return 68
