from core.targets import classify_target


metadata = {
    "name": "Intel Assistant",
    "description": "Local analyst brain that turns a target into an operation plan, collection priorities, risk hypotheses, and recommended flows.",
    "category": "planning",
    "target_types": ["any"],
    "tags": ["assistant", "triage", "planning", "local-ai"],
    "passive": True,
    "risk": "low",
}


async def run(target: str, mode: str = "standard") -> dict:
    profile = classify_target(target)
    playbook = _playbook(profile.kind, mode)
    hypotheses = _hypotheses(profile, mode)
    priority_tasks = _priority_tasks(profile, mode)
    recommended_flows = _flows(profile.kind, mode)

    return {
        "status": "success",
        "summary": f"{len(priority_tasks)} task(s), {len(hypotheses)} hypothesis hint(s), {len(recommended_flows)} flow(s) recommended.",
        "data": {
            "target": target,
            "target_type": profile.kind,
            "mode": mode,
            "confidence": _confidence(profile.kind),
            "operation_profile": playbook,
            "priority_tasks": priority_tasks,
            "hypotheses": hypotheses,
            "flow_hints": recommended_flows,
            "collection_plan": _collection_plan(profile.kind, mode),
            "guardrails": [
                "Use active/aggressive mode only on authorized targets.",
                "Avoid login bypass, credential stuffing, private API abuse, and reset/register probing.",
                "Preserve raw outputs and graph snapshots for auditability.",
            ],
            "signals": [
                {"type": "task", "value": item["task"], "priority": item["priority"]}
                for item in priority_tasks
            ] + [
                {"type": "hypothesis", "value": item["title"], "confidence": item["confidence"]}
                for item in hypotheses
            ],
        },
    }


def _playbook(kind: str, mode: str) -> dict:
    base = {
        "objective": "Build a validated entity graph before deep pivots.",
        "style": "graph-first",
        "mode": mode,
        "pace": "high" if mode == "aggressive" else "controlled",
    }
    if kind in {"domain", "url"}:
        base.update({"focus": "infrastructure surface", "primary_risks": ["exposed admin surface", "weak mail posture", "third-party app links"]})
    elif kind in {"username", "email"}:
        base.update({"focus": "identity surface", "primary_risks": ["profile reuse", "developer footprint", "workspace/provider exposure"]})
    elif kind == "phone":
        base.update({"focus": "telecom pattern triage", "primary_risks": ["country attribution ambiguity", "reuse in public profiles"]})
    else:
        base.update({"focus": "target classification", "primary_risks": ["insufficient entity typing"]})
    return base


def _priority_tasks(profile, mode: str) -> list[dict]:
    tasks = []
    if profile.kind in {"username", "email", "unknown"}:
        tasks.extend(
            [
                {"priority": "P1", "task": "Run identity expansion and username presence sweep.", "flow": "identity_surface"},
                {"priority": "P1", "task": "Confirm high-confidence profile matches before branching.", "flow": "identity_deep"},
                {"priority": "P2", "task": "Pivot developer and package registries for reusable handles.", "flow": "identity_deep"},
            ]
        )
    if profile.kind in {"domain", "url", "email"}:
        tasks.extend(
            [
                {"priority": "P1", "task": "Map DNS, RDAP, CT logs, mail posture, and website metadata.", "flow": "domain_surface"},
                {"priority": "P2", "task": "Check app links and well-known files for mobile/cloud pivots.", "flow": "domain_surface"},
            ]
        )
    if mode in {"active", "aggressive"} and profile.kind in {"domain", "url", "email"}:
        tasks.append({"priority": "P1", "task": "Run active surface sweep for common hosts and sensitive paths.", "flow": "active_domain_recon"})
    if profile.kind == "phone":
        tasks.append({"priority": "P1", "task": "Normalize phone shape and preserve country-code hypothesis.", "flow": "phone_triage"})
    return tasks[:8]


def _hypotheses(profile, mode: str) -> list[dict]:
    items = []
    if profile.email:
        items.append({"title": "Email local-part may be reused as public username.", "confidence": 0.76})
        items.append({"title": "Email domain can reveal workspace provider and organization surface.", "confidence": 0.68})
    if profile.username:
        items.append({"title": "Username reuse across developer/social platforms may create strong identity links.", "confidence": 0.72})
    if profile.domain:
        items.append({"title": "Domain may expose subdomains through CT logs and common host conventions.", "confidence": 0.71})
        items.append({"title": "Well-known files may reveal app package IDs, security contacts, or API surfaces.", "confidence": 0.62})
    if mode == "aggressive":
        items.append({"title": "Aggressive public probing can reveal sensitive but unauthenticated endpoints.", "confidence": 0.58})
    return items[:8]


def _flows(kind: str, mode: str) -> list[dict]:
    mapping = {
        "username": ["identity_surface", "identity_deep"],
        "email": ["identity_surface", "identity_deep", "domain_surface"],
        "domain": ["domain_surface", "active_domain_recon"],
        "url": ["domain_surface", "active_domain_recon"],
        "phone": ["phone_triage"],
    }
    flow_ids = mapping.get(kind, ["identity_surface"])
    if mode == "standard":
        flow_ids = [item for item in flow_ids if item != "active_domain_recon"]
    return [{"flow_id": flow_id, "reason": f"{kind}_{mode}_triage"} for flow_id in flow_ids]


def _collection_plan(kind: str, mode: str) -> list[str]:
    plan = ["Classify target", "Build initial graph", "Review high-confidence nodes", "Save graph to case"]
    if kind in {"domain", "url"}:
        plan.extend(["Run DNS/RDAP/CT enrichers", "Review website surface", "Assess mail posture"])
    if kind in {"username", "email"}:
        plan.extend(["Generate handle variants", "Run username/account presence", "Review profile links"])
    if mode in {"active", "aggressive"}:
        plan.extend(["Run active read-only sweep", "Review sensitive paths", "Throttle or stop if rate-limited"])
    return plan


def _confidence(kind: str) -> str:
    if kind in {"email", "domain", "url"}:
        return "high"
    if kind in {"username", "phone"}:
        return "medium"
    return "low"
