from __future__ import annotations

from typing import Any

from backend.investigator.types import InvestigationPlan, NextAction


class Planner:
    def next_actions(self, graph: dict[str, Any], validation: dict[str, Any], noise: dict[str, Any], hypotheses: list[dict[str, Any]], transforms: list[dict[str, Any]], api_keys: set[str], selected_entity_id: str | None = None, mode: str = "balanced") -> InvestigationPlan:
        nodes = graph.get("nodes") or []
        by_type: dict[str, list[dict[str, Any]]] = {}
        for node in nodes:
            by_type.setdefault(str(node.get("type") or "unknown").lower(), []).append(node)
        gaps: list[str] = []
        actions: list[NextAction] = []

        def add(action_id: str, label: str, transform_id: str | None, node: dict[str, Any] | None, why: str, outputs: list[str], required: str | None = None, noise_risk: str = "low", run: bool = False) -> None:
            actions.append(NextAction(action_id, label, transform_id, str(node.get("id")) if node else selected_entity_id, why, outputs, "low local cost" if not required else "connector quota", required, noise_risk, "Passive public-source or official BYOK only; no account-state-changing probes.", mode, run and not required))

        if by_type.get("email") and not by_type.get("domain"):
            gaps.append("Email exists but mail/domain posture is thin")
            add("email_workspace", "Resolve mailbox domain and workspace posture", "email_to_workspace", by_type["email"][0], "Email investigations need MX/TXT/provider context before identity conclusions.", ["domain", "mx_record", "workspace_signal"])
        if by_type.get("domain") and not by_type.get("ip"):
            gaps.append("Domain exists but no IP/DNS expansion")
            add("domain_dns", "Collect DNS and RDAP infrastructure", "domain_to_dns", by_type["domain"][0], "Infrastructure pivots provide stronger technical evidence than profile candidates.", ["dns_record", "ip", "mx_record"])
        if by_type.get("username") and not by_type.get("profile"):
            gaps.append("Username exists but public profile confirmation is thin")
            add("username_profiles", "Run public profile resolution", "username_to_profiles", by_type["username"][0], "A handle alone is not evidence; public profile confirmation is needed.", ["profile", "public_profile"], noise_risk="medium")
        if validation.get("counts", {}).get("WEAK") or validation.get("counts", {}).get("INSUFFICIENT_EVIDENCE"):
            add("validate_weak", "Review weak findings and evidence gaps", None, None, "Weak findings should be validated before reporting or graph expansion.", ["validation_report"], noise_risk="low")
        if noise.get("removed_count", 0):
            add("inspect_noise", "Review suppressed noise bin", None, None, "Suppressed artifacts may contain context but should not clutter graph.", ["noise_report"], noise_risk="low")
        if hypotheses:
            add("test_hypotheses", "Test active hypotheses", None, None, "Hypotheses below 90 need direct corroborating evidence before analyst acceptance.", ["supporting_evidence", "contradictions"], noise_risk="medium")
        for transform in transforms:
            missing = [key for key in transform.get("required_keys") or [] if key not in api_keys]
            if missing and selected_entity_id and not any(action.required_api_key for action in actions):
                add("configure_key", f"Configure {missing[0]} for {transform.get('label')}", str(transform.get("id")), None, "Connector is disabled until operator provides BYOK credentials.", list(transform.get("output_types") or []), missing[0], "low")
                break
        if not actions:
            add("report_ready", "Prepare analyst packet", None, None, "Current graph has no obvious collection gap from deterministic checks.", ["report"], noise_risk="low")
        warnings = []
        if mode == "deep":
            warnings.append("Deep mode expands coverage but still requires passive/legal transforms and analyst confirmation.")
        return InvestigationPlan(mode, actions[:8], gaps, warnings)
