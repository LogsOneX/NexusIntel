import asyncio
import time
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional

from core.engine import AnalyticsEngine
from core.graph import build_investigation_graph
from core.targets import TargetProfile, classify_target


FLOW_TEMPLATES: Dict[str, dict] = {
    "identity_deep": {
        "id": "identity_deep",
        "name": "Identity Deep Pivot",
        "description": "Username/email to permutations, public profiles, account-presence hints, developer analytics, and app/workspace pivots.",
        "input_types": ["username", "email", "url"],
        "steps": [
            {"id": "intel_brief", "name": "Intel Brief", "modules": ["intel_assistant"], "target_types": ["username", "email", "url"], "outputs": ["flow", "task"]},
            {"id": "identity_expansion", "name": "Identity Expansion", "modules": ["identity_expansion"], "target_types": ["username", "email", "url"], "outputs": ["username", "domain"]},
            {"id": "identity_presence", "name": "Account Presence", "modules": ["account_presence", "username_presence"], "target_types": ["username", "email", "url"], "outputs": ["url", "profile", "service"]},
            {"id": "developer_enrichment", "name": "Developer Enrichment", "modules": ["account_pivots", "user_analytics"], "target_types": ["username", "email", "domain"], "outputs": ["profile", "url", "domain"]},
        ],
    },
    "identity_surface": {
        "id": "identity_surface",
        "name": "Identity Surface",
        "description": "Fast local-first identity expansion plus broad username/account checks.",
        "input_types": ["username", "email", "url", "unknown"],
        "steps": [
            {"id": "intel_brief", "name": "Intel Brief", "modules": ["intel_assistant"], "target_types": ["username", "email", "url", "unknown"], "outputs": ["flow", "task"]},
            {"id": "expand", "name": "Expand Seeds", "modules": ["identity_expansion"], "target_types": ["username", "email", "url", "unknown"], "outputs": ["username", "domain"]},
            {"id": "presence", "name": "Presence Sweep", "modules": ["username_presence", "account_presence"], "target_types": ["username", "email", "url"], "outputs": ["url", "profile", "service"]},
        ],
    },
    "domain_surface": {
        "id": "domain_surface",
        "name": "Domain Surface",
        "description": "Domain to DNS, RDAP, CT, website, headers, IP ownership, and graph links.",
        "input_types": ["domain", "url", "email"],
        "steps": [
            {"id": "domain_foundation", "name": "Infrastructure Foundation", "modules": ["domain_intelligence", "network_mapping", "header_diagnostics"], "target_types": ["domain", "url", "email"], "outputs": ["ip", "hostname", "dns_record", "risk"]},
            {"id": "website_surface", "name": "Website Surface", "modules": ["website_surface"], "target_types": ["domain", "url"], "outputs": ["url", "email", "tracker"]},
            {"id": "active_surface", "name": "Active Surface", "modules": ["active_surface"], "target_types": ["domain", "url", "email"], "outputs": ["hostname", "url", "risk"]},
            {"id": "ip_ownership", "name": "IP Ownership", "modules": ["ip_asn_lookup"], "target_types": ["ip", "domain", "url", "email"], "outputs": ["ip", "organization", "asn", "cidr"]},
        ],
    },
    "active_domain_recon": {
        "id": "active_domain_recon",
        "name": "Active Domain Recon",
        "description": "Authorized active DNS/HTTP surface sweep chained into website and ownership enrichment.",
        "input_types": ["domain", "url", "email"],
        "steps": [
            {"id": "active_surface", "name": "Active Surface Sweep", "modules": ["active_surface"], "target_types": ["domain", "url", "email"], "outputs": ["hostname", "url", "risk"]},
            {"id": "website_surface", "name": "Website Surface", "modules": ["website_surface", "header_diagnostics"], "target_types": ["domain", "url"], "outputs": ["url", "email", "tracker"]},
            {"id": "ownership", "name": "Ownership", "modules": ["domain_intelligence", "ip_asn_lookup"], "target_types": ["domain", "url", "email"], "outputs": ["ip", "hostname", "organization", "asn"]},
        ],
    },
    "phone_triage": {
        "id": "phone_triage",
        "name": "Phone Triage",
        "description": "Offline phone normalization and signal extraction.",
        "input_types": ["phone"],
        "steps": [
            {"id": "phone_pattern", "name": "Phone Pattern", "modules": ["phone_intel"], "target_types": ["phone"], "outputs": ["signal"]},
        ],
    },
}


def list_flows() -> List[dict]:
    return [FLOW_TEMPLATES[key] for key in sorted(FLOW_TEMPLATES)]


async def run_flow(flow_id: str, target: str, timeout: int = 18, concurrency: int = 6, mode: str = "standard") -> dict:
    if flow_id not in FLOW_TEMPLATES:
        raise ValueError(f"Unknown flow: {flow_id}")

    flow = FLOW_TEMPLATES[flow_id]
    scan_id = f"flow-{int(time.time() * 1000)}"
    created_at = datetime.now(timezone.utc).isoformat()
    initial_profile = classify_target(target)
    current_targets = [target]
    all_results: Dict[str, dict] = {}
    execution_log: List[dict] = []
    branch_steps: List[dict] = []

    for depth, step in enumerate(flow["steps"]):
        selected = _select_targets(current_targets, step.get("target_types", []))
        if not selected:
            selected = [target]

        step_outputs = []
        for value in selected[:8]:
            profile = classify_target(value)
            engine = AnalyticsEngine(module_timeout=timeout, max_concurrent=concurrency, mode=mode)
            engine.load_modules(include=step.get("modules"))
            started = time.perf_counter()
            results = await engine.execute_all(value, profile=profile)
            elapsed_ms = int((time.perf_counter() - started) * 1000)

            for module_name, payload in results.items():
                all_results[f"{step['id']}::{value}::{module_name}"] = payload

            graph = build_investigation_graph(profile, results)
            new_targets = _targets_from_graph(graph, step.get("outputs", []))
            current_targets.extend(item for item in new_targets if item not in current_targets)
            step_outputs.extend(new_targets)

            execution_log.append(
                {
                    "step_id": f"{step['id']}::{value}",
                    "branch_id": "branch-0",
                    "branch_name": "Main Flow",
                    "node_id": step["id"],
                    "enricher_name": ",".join(step.get("modules", [])),
                    "inputs": [value],
                    "outputs": step_outputs,
                    "status": "completed" if all(item.get("status") != "error" for item in results.values()) else "partial",
                    "error": None,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "execution_time_ms": elapsed_ms,
                    "cache_hit": False,
                    "mode": mode,
                }
            )

        branch_steps.append(
            {
                "nodeId": step["id"],
                "name": step["name"],
                "params": {},
                "type": "enricher",
                "inputs": {"targets": selected},
                "outputs": {"targets": sorted(set(step_outputs))},
                "status": "completed",
                "branchId": "branch-0",
                "depth": depth,
            }
        )

    final_graph = build_investigation_graph(initial_profile, all_results)
    completed = sum(1 for item in execution_log if item["status"] in {"completed", "partial"})
    failed = sum(1 for item in execution_log if item["status"] == "failed")
    return {
        "scan_id": scan_id,
        "flow": flow,
        "target_profile": initial_profile.__dict__,
        "created_at": created_at,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "status": "completed" if not failed else "partial",
        "enricher_branches": [{"id": "branch-0", "name": "Main Flow", "steps": branch_steps}],
        "execution_log": execution_log,
        "summary": {
            "total_steps": len(execution_log),
            "completed_steps": completed,
            "failed_steps": failed,
            "total_execution_time_ms": sum(item["execution_time_ms"] for item in execution_log),
            "mode": mode,
        },
        "final_results": {
            "initial_values": [target],
            "discovered_targets": sorted(set(current_targets)),
            "results": all_results,
        },
        "results": all_results,
        "graph": final_graph,
    }


def _select_targets(values: Iterable[str], target_types: List[str]) -> List[str]:
    selected = []
    for value in values:
        profile = classify_target(value)
        if not target_types or profile.kind in target_types:
            selected.append(value)
    return selected


def _targets_from_graph(graph: dict, output_types: Optional[List[str]]) -> List[str]:
    wanted = set(output_types or [])
    values = []
    for node in graph.get("nodes", []):
        node_type = node.get("type")
        if wanted and node_type not in wanted:
            continue
        properties = node.get("properties") or node.get("nodeProperties") or {}
        if isinstance(properties, dict) and properties.get("method") == "manual_review":
            continue
        label = str(node.get("label", "")).strip()
        if not label or label.startswith(("domain_", "header_", "network_", "username_", "user_", "phone_")):
            continue
        if node_type in {"ip", "domain", "url", "email", "username", "phone", "hostname"}:
            values.append(label)
    return values[:30]


def run_flow_sync(flow_id: str, target: str, timeout: int = 18, concurrency: int = 6, mode: str = "standard") -> dict:
    return asyncio.run(run_flow(flow_id, target, timeout=timeout, concurrency=concurrency, mode=mode))
