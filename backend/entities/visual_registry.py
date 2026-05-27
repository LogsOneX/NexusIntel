from __future__ import annotations

from backend.entities.registry import ENTITY_DEFINITIONS

def visual_registry() -> dict[str, dict]:
    return {item["id"]: {"icon": item["visual_icon"], "color": item["graph_color"], "accent": item["graph_accent"], "family": item["family"]} for item in ENTITY_DEFINITIONS}
