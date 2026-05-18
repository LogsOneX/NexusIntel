import sys
from pathlib import Path
from typing import Any

from core.engine import AnalyticsEngine
from core.flows import list_flows
from core.schemas import get_entity_types
from core.vault import vault_status


def readiness_report() -> dict[str, Any]:
    engine = AnalyticsEngine()
    engine.load_modules()
    modules = engine.catalog()
    flows = list_flows()
    types = get_entity_types()
    vault = vault_status()

    checks = [
        _check("modules_loaded", len(modules) >= 10, f"{len(modules)} module(s) available"),
        _check("identity_modules", _count_category(modules, "identity") >= 5, f"{_count_category(modules, 'identity')} identity module(s)"),
        _check("infrastructure_modules", _count_category(modules, "infrastructure") >= 5, f"{_count_category(modules, 'infrastructure')} infrastructure module(s)"),
        _check("flow_templates", len(flows) >= 4, f"{len(flows)} flow template(s)"),
        _check("entity_types", len(types) >= 16, f"{len(types)} entity type(s)"),
        _check("active_surface", any(item["name"] == "active_surface" for item in modules), "active surface module present"),
        _check("intel_assistant", any(item["name"] == "intel_assistant" for item in modules), "local analyst brain present"),
        _check("results_dir", _writable(Path("results")), "results directory writable"),
        _check("reports_dir", _writable(Path("reports")), "reports directory writable"),
        _check("local_store", _writable(Path(".nexusrecon")), "local case/vault storage writable"),
        _check("vault", isinstance(vault.get("keys", []), list), f"{len(vault.get('keys', []))} vault key(s) configured"),
        _check("python", sys.version_info >= (3, 10), f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"),
    ]
    failed = [item for item in checks if item["status"] == "fail"]
    warn = [item for item in checks if item["status"] == "warn"]
    return {
        "status": "ready" if not failed else "blocked",
        "score": max(0, int(((len(checks) - len(failed) - (len(warn) * 0.5)) / len(checks)) * 100)),
        "checks": checks,
        "summary": {
            "modules": len(modules),
            "flows": len(flows),
            "entity_types": len(types),
            "vault_keys": len(vault.get("keys", [])),
        },
    }


def _count_category(modules: list[dict], category: str) -> int:
    return sum(1 for item in modules if item.get("category") == category)


def _check(name: str, ok: bool, detail: str, warn: bool = False) -> dict[str, str]:
    status = "ok" if ok else "warn" if warn else "fail"
    return {"name": name, "status": status, "detail": detail}


def _writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".readiness"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except OSError:
        return False
