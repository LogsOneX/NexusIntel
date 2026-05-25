from __future__ import annotations

from typing import Any

from backend.playbooks.registry import get_playbook, list_playbooks
from backend.playbooks.types import PlaybookPlan


class PlaybookEngine:
    def list(self) -> list[dict[str, Any]]:
        return list_playbooks()

    def plan(self, investigation_id: str, playbook_id: str, graph: dict[str, Any], transforms: list[dict[str, Any]], api_keys: set[str]) -> dict[str, Any]:
        playbook = get_playbook(playbook_id)
        if not playbook:
            raise KeyError(playbook_id)
        transform_by_id = {str(item.get("id")): item for item in transforms}
        node_types = {str(node.get("type") or "unknown").lower() for node in graph.get("nodes") or []}
        compatible = "*" in playbook.input_types or bool(node_types & {kind.lower() for kind in playbook.input_types})
        runnable: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        confirm: list[dict[str, Any]] = []
        for step in playbook.steps:
            row = step.to_dict()
            transform = transform_by_id.get(str(step.transform_id)) if step.transform_id else None
            missing = [key for key in (transform or {}).get("required_keys", []) if key not in api_keys]
            if not compatible:
                row["disabled_reason"] = f"Playbook expects {', '.join(playbook.input_types)} but graph has {', '.join(sorted(node_types)) or 'no entities'}"
                blocked.append(row)
            elif missing:
                row["disabled_reason"] = f"Missing API key(s): {', '.join(missing)}"
                blocked.append(row)
            elif step.requires_confirmation:
                row["confirmation_reason"] = "Broad/deep expansion requires analyst confirmation before execution."
                confirm.append(row)
            else:
                runnable.append(row)
        return PlaybookPlan(playbook_id, investigation_id, runnable, blocked, confirm, playbook.stop_conditions, playbook.output_report_sections).to_dict()

    def run(self, investigation_id: str, playbook_id: str, graph: dict[str, Any], transforms: list[dict[str, Any]], api_keys: set[str], confirmed: bool = False) -> dict[str, Any]:
        plan = self.plan(investigation_id, playbook_id, graph, transforms, api_keys)
        queued = list(plan["runnable_steps"])
        if confirmed:
            queued.extend(plan["required_confirmation"])
        return {**plan, "status": "planned", "queued_steps": queued, "executed": False, "note": "Playbook execution is planned only; transforms are not auto-run without explicit analyst dispatch."}
