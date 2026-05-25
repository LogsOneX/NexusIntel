from __future__ import annotations

import json
import os
import time
from typing import Any

import httpx

from backend.investigator.model_profiles import get_profile
from backend.investigator.types import LocalLLMRequest, LocalLLMResponse


def ai_settings(settings: dict[str, Any]) -> dict[str, Any]:
    legacy = settings.get("llm") if isinstance(settings.get("llm"), dict) else {}
    ai = settings.get("ai") if isinstance(settings.get("ai"), dict) else {}
    return {
        "mode": os.getenv("NEXUS_AI_MODE", ai.get("mode") or legacy.get("provider") or "rules"),
        "endpoint": os.getenv("NEXUS_AI_ENDPOINT", ai.get("endpoint") or legacy.get("endpoint") or "http://localhost:11434"),
        "model": os.getenv("NEXUS_AI_MODEL", ai.get("model") or legacy.get("model") or ""),
        "context_tokens": int(os.getenv("NEXUS_AI_CONTEXT_TOKENS", str(ai.get("context_tokens") or 4096))),
        "max_tokens": int(os.getenv("NEXUS_AI_MAX_TOKENS", str(ai.get("max_tokens") or 700))),
        "temperature": float(os.getenv("NEXUS_AI_TEMPERATURE", str(ai.get("temperature") or 0.1))),
        "ram_profile": os.getenv("NEXUS_AI_RAM_PROFILE", ai.get("ram_profile") or "tiny"),
        "enable_summarization": str(os.getenv("NEXUS_AI_ENABLE_SUMMARIZATION", str(ai.get("enable_summarization", True)))).lower() != "false",
        "enable_json_mode": str(os.getenv("NEXUS_AI_ENABLE_JSON_MODE", str(ai.get("enable_json_mode", True)))).lower() != "false",
        "api_key": ai.get("api_key") or legacy.get("api_key") or os.getenv("NEXUS_AI_API_KEY", ""),
    }


def compact_json(payload: Any, limit: int) -> str:
    text = json.dumps(payload, default=str, separators=(",", ":"))
    return text[:limit]


class LocalLLMClient:
    async def complete(self, request: LocalLLMRequest, settings: dict[str, Any]) -> LocalLLMResponse:
        config = ai_settings(settings)
        mode = str(config["mode"]).lower()
        if mode in {"rules", "local", "none", ""} or not config.get("model"):
            return LocalLLMResponse("rules", "rules", None, "", parsed_json=None, fallback=True)
        started = time.perf_counter()
        endpoint = str(config.get("endpoint") or "").rstrip("/")
        model = str(config.get("model") or "")
        headers = {"Content-Type": "application/json"}
        if config.get("api_key"):
            headers["Authorization"] = f"Bearer {config['api_key']}"
        try:
            async with httpx.AsyncClient(timeout=35) as client:
                if mode == "ollama":
                    response = await client.post(f"{endpoint}/api/chat", json={"model": model, "stream": False, "format": "json" if request.json_mode else None, "messages": [{"role": "system", "content": request.system_prompt}, {"role": "user", "content": request.prompt}], "options": {"temperature": request.temperature, "num_predict": request.max_tokens}}, headers=headers)
                    response.raise_for_status()
                    content = response.json().get("message", {}).get("content", "")
                elif mode == "llamacpp":
                    response = await client.post(f"{endpoint}/completion", json={"prompt": f"{request.system_prompt}\n\n{request.prompt}", "n_predict": request.max_tokens, "temperature": request.temperature}, headers=headers)
                    response.raise_for_status()
                    content = response.json().get("content", "")
                else:
                    response = await client.post(f"{endpoint.rstrip('/')}/chat/completions", json={"model": model, "messages": [{"role": "system", "content": request.system_prompt}, {"role": "user", "content": request.prompt}], "temperature": request.temperature, "max_tokens": request.max_tokens, "response_format": {"type": "json_object"} if request.json_mode else None}, headers=headers)
                    response.raise_for_status()
                    content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            parsed = None
            if request.json_mode and content:
                try:
                    parsed = json.loads(content)
                except Exception:
                    parsed = None
            return LocalLLMResponse(mode, mode, model, content, parsed, int((time.perf_counter() - started) * 1000), False)
        except Exception as exc:
            return LocalLLMResponse(mode, mode, model, "", parsed_json=None, elapsed_ms=int((time.perf_counter() - started) * 1000), fallback=True, error=str(exc))


def model_status(settings: dict[str, Any]) -> dict[str, Any]:
    config = ai_settings(settings)
    profile = get_profile(config.get("ram_profile"))
    return {"mode": config["mode"], "endpoint": config["endpoint"], "model": config.get("model") or "rules-only", "ram_profile": profile.to_dict(), "context_budget": min(int(config["context_tokens"]), profile.max_context), "max_tokens": config["max_tokens"], "temperature": config["temperature"], "summarization": config["enable_summarization"], "json_mode": config["enable_json_mode"], "fallback": str(config["mode"]).lower() in {"rules", "local", "none", ""} or not config.get("model")}
