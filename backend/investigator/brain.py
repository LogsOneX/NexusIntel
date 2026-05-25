from __future__ import annotations

import json
from typing import Any

from backend.investigator.evidence_reasoner import EvidenceReasoner
from backend.investigator.hypothesis import HypothesisEngine
from backend.investigator.local_llm import LocalLLMClient, ai_settings, compact_json, model_status
from backend.investigator.memory import InvestigatorMemory
from backend.investigator.model_profiles import get_profile
from backend.investigator.noise_killer import NoiseKiller
from backend.investigator.planner import Planner
from backend.investigator.prompts import JSON_OUTPUT_SCHEMA_NOTE, SYSTEM_PROMPTS
from backend.investigator.report import ReportReadinessEngine
from backend.investigator.types import EvidenceCitation, InvestigatorAnswer, InvestigatorQuestion, LocalLLMRequest
from backend.investigator.validator import Validator


class InvestigatorBrain:
    def __init__(self) -> None:
        self.reasoner = EvidenceReasoner()
        self.noise = NoiseKiller()
        self.validator = Validator()
        self.hypotheses = HypothesisEngine()
        self.planner = Planner()
        self.memory = InvestigatorMemory()
        self.report = ReportReadinessEngine()
        self.llm = LocalLLMClient()

    def analyze(self, state: dict[str, Any], selected_entity_id: str | None = None, plan_mode: str = "balanced") -> dict[str, Any]:
        graph = state.get("graph") or {"nodes": [], "edges": []}
        evidence = state.get("evidence") or []
        validation = self.validator.validate_graph(graph, evidence, selected_entity_id)
        noise = self.noise.report(graph.get("nodes") or [], graph.get("noise") or state.get("noise") or [])
        hypotheses = [item.to_dict() for item in self.hypotheses.generate(graph, validation)]
        plan = self.planner.next_actions(graph, validation, noise, hypotheses, state.get("transforms") or [], set(state.get("api_keys") or []), selected_entity_id, plan_mode).to_dict()
        readiness = self.report.score(graph, validation, noise, hypotheses, evidence)
        reasoned = self.reasoner.reason(graph, evidence, selected_entity_id)
        return {"reasoned_evidence": reasoned, "validation": validation, "noise": noise, "hypotheses": hypotheses, "plan": plan, "report_readiness": readiness, "model_status": model_status(state.get("settings") or {})}

    def deterministic_reply(self, question: InvestigatorQuestion, analysis: dict[str, Any]) -> str:
        validation_counts = analysis["validation"].get("counts", {})
        noise_count = analysis["noise"].get("removed_count", 0)
        next_actions = analysis["plan"].get("next_actions", [])[:3]
        hypotheses = analysis.get("hypotheses", [])[:3]
        parts = [
            f"Validation posture: {validation_counts or 'no graph findings yet'}.",
            f"Noise removed: {noise_count} item(s).",
            f"Report readiness: {analysis['report_readiness'].get('score', 0)}%.",
        ]
        if hypotheses:
            parts.append("Active hypotheses: " + "; ".join(f"{item['statement']} ({item['confidence_score']}%)" for item in hypotheses))
        if next_actions:
            parts.append("Next actions: " + "; ".join(f"{item['label']} - {item['why']}" for item in next_actions))
        if not analysis["reasoned_evidence"].get("evidence_count"):
            parts.append("Insufficient evidence: no evidence vault records are attached; treat manual/root nodes as unverified until corroborated.")
        return " ".join(parts)

    async def answer(self, question: InvestigatorQuestion, state: dict[str, Any]) -> dict[str, Any]:
        analysis = self.analyze(state, question.selected_entity_id, question.mode)
        settings = state.get("settings") or {}
        config = ai_settings(settings)
        profile = get_profile(config.get("ram_profile"))
        prompt_payload = {
            "question": question.prompt,
            "validation": analysis["validation"],
            "noise": {"removed_count": analysis["noise"].get("removed_count"), "top": analysis["noise"].get("items", [])[:8]},
            "hypotheses": analysis["hypotheses"][:8],
            "next_actions": analysis["plan"].get("next_actions", [])[:8],
            "report_readiness": analysis["report_readiness"],
            "evidence_cards": (state.get("evidence") or [])[:16],
        }
        deterministic = self.deterministic_reply(question, analysis)
        custom_prompt = ""
        ai_block = settings.get("ai") if isinstance(settings.get("ai"), dict) else {}
        if isinstance(ai_block, dict):
            custom_prompt = str(ai_block.get("custom_system_prompt") or "").strip()
        system_prompt = custom_prompt or SYSTEM_PROMPTS["cybercrime_investigator"]
        request = LocalLLMRequest(compact_json(prompt_payload, min(config["context_tokens"] * 4, profile.max_context * 4)) + "\n" + JSON_OUTPUT_SCHEMA_NOTE, system_prompt, profile, bool(config.get("enable_json_mode")), min(int(config["max_tokens"]), profile.default_max_tokens), float(config["temperature"]))
        llm_response = await self.llm.complete(request, settings)
        reply = deterministic
        commands: list[dict[str, Any]] = []
        warnings = []
        if llm_response.parsed_json:
            summary = llm_response.parsed_json.get("summary")
            if summary:
                reply = str(summary)
            for action in llm_response.parsed_json.get("next_actions") or []:
                if isinstance(action, dict):
                    commands.append({"type": "suggest_transform", "transform": action.get("transform_id") or action.get("transform"), "reason": action.get("reason") or action.get("why")})
            warnings.extend(str(item) for item in llm_response.parsed_json.get("warnings") or [])
        elif llm_response.error:
            warnings.append(f"Local LLM unavailable; rules-only answer used: {llm_response.error}")
        refs: list[EvidenceCitation] = []
        seen_refs: set[str] = set()
        for node in analysis["reasoned_evidence"].get("node_evidence", {}).values():
            for ref in node.get("evidence_refs") or []:
                if not isinstance(ref, dict):
                    continue
                key = str(ref.get("evidence_id") or ref.get("payload_sha256") or ref.get("source_url") or ref)
                if key in seen_refs:
                    continue
                seen_refs.add(key)
                refs.append(EvidenceCitation(str(ref.get("evidence_id")) if ref.get("evidence_id") else None, str(ref.get("source") or "unknown"), str(ref.get("source_url")) if ref.get("source_url") else None, str(ref.get("payload_sha256")) if ref.get("payload_sha256") else None, str(ref.get("fetched_at")) if ref.get("fetched_at") else None, str(ref.get("note") or "evidence cited by deterministic reasoner")))
        return InvestigatorAnswer(reply, llm_response.provider, llm_response.mode, refs[:20], analysis["validation"], {"removed_count": analysis["noise"].get("removed_count", 0), "items": analysis["noise"].get("items", [])[:12]}, analysis["hypotheses"][:12], analysis["plan"].get("next_actions", [])[:12], commands, warnings + analysis["report_readiness"].get("warnings", []), analysis["report_readiness"]).to_dict()
