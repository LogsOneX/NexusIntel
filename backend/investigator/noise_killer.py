from __future__ import annotations

import re
from typing import Any

from backend.investigator.types import EvidenceCitation, NoiseDecision

GENERIC_LOGIN = ("login", "sign in", "signup", "register", "forgot password", "reset password")
AUTH_WALL = ("login required", "sign in to continue", "authenticate", "you must be logged in", "403", "401")
SOFT_404 = ("not found", "404", "does not exist", "user not found", "profile not found", "page unavailable")
PARKED = ("parked", "buy this domain", "domain for sale", "sedo", "afternic", "parkingcrew")
CDN = ("cloudflare", "akamai", "fastly", "cloudfront", "googleusercontent", "azureedge", "cdn77", "bunnycdn")
REGISTRAR_PRIVACY = ("privacy", "redacted", "whoisguard", "domains by proxy", "identity protect", "contact privacy")
GENERIC_NS_MX = ("google.com", "outlook.com", "secureserver.net", "cloudflare.com", "registrar-servers.com")
DEEPLINK = ("wa.me", "t.me", "telegram", "whatsapp", "viber")


def _blob(item: dict[str, Any]) -> str:
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    artifact = data.get("artifact") if isinstance(data.get("artifact"), dict) else {}
    return " ".join(str(part) for part in [item.get("type"), item.get("label"), item.get("value"), item.get("source"), data, artifact]).lower()


def _citation(item: dict[str, Any]) -> list[EvidenceCitation]:
    data = item.get("data") if isinstance(item.get("data"), dict) else {}
    artifact = data.get("artifact") if isinstance(data.get("artifact"), dict) else {}
    ref = data.get("raw_evidence_ref") or artifact.get("raw_evidence_ref") or data.get("evidence_id")
    if not ref:
        return []
    return [EvidenceCitation(str(ref), str(item.get("source") or artifact.get("source") or "unknown"), str(data.get("source_url") or artifact.get("source_url") or "") or None, str(data.get("payload_sha256") or artifact.get("payload_sha256") or "") or None, str(data.get("fetched_at") or item.get("created_at") or "") or None)]


class NoiseKiller:
    def decide(self, item: dict[str, Any]) -> NoiseDecision:
        node_type = str(item.get("type") or "unknown").lower()
        confidence = str(item.get("confidence") or "").lower()
        data = item.get("data") if isinstance(item.get("data"), dict) else {}
        score = 0
        reasons: list[str] = []
        blob = _blob(item)
        status = str(data.get("status_code") or data.get("http_status") or "")

        if any(marker in blob for marker in SOFT_404):
            score += 55
            reasons.append("soft 404 / profile not found marker")
        if any(marker in blob for marker in AUTH_WALL) or status in {"401", "403"}:
            score += 45
            reasons.append("auth wall only without target-specific public evidence")
        if any(marker in blob for marker in GENERIC_LOGIN) and node_type in {"profile", "public_profile", "url", "web_fingerprint"}:
            score += 35
            reasons.append("generic login/sign-up page")
        if any(marker in blob for marker in PARKED):
            score += 60
            reasons.append("parked/domain-for-sale page")
        if node_type == "ip" and any(marker in blob for marker in CDN):
            score += 35
            reasons.append("CDN/shared edge infrastructure")
        if node_type in {"rdap_record", "domain", "nameserver"} and any(marker in blob for marker in REGISTRAR_PRIVACY):
            score += 22
            reasons.append("registrar privacy-only registration data")
        if node_type in {"mx_record", "nameserver", "dns_record"} and any(marker in blob for marker in GENERIC_NS_MX):
            score += 18
            reasons.append("generic provider node with low investigative value")
        if node_type in {"public_deeplink", "phone_deeplink_candidate"} and any(marker in blob for marker in DEEPLINK):
            score += 45
            reasons.append("messenger deeplink landing page is not registration proof")
        if node_type.endswith("candidate") or "candidate" in node_type or confidence in {"candidate", "weak", "low"}:
            score += 25
            reasons.append("candidate/low-confidence artifact")
        if re.search(r"\{username\}|\{target\}|example\.", blob):
            score += 55
            reasons.append("template-generated URL or placeholder marker")
        if not data and node_type not in {"email", "domain", "ip", "phone", "username"}:
            score += 20
            reasons.append("empty metadata page")

        if score >= 70:
            action = "suppress"
        elif score >= 45:
            action = "escalate_to_candidate"
        elif score >= 25:
            action = "require_manual_review"
        else:
            action = "keep_as_context"
        return NoiseDecision(score >= 50, min(100, score), reasons or ["no major noise marker detected"], action, [str(item.get("id"))] if item.get("id") else [], _citation(item))

    def report(self, nodes: list[dict[str, Any]], noise: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        decisions = [self.decide(node) for node in nodes]
        for item in noise or []:
            decision = self.decide(item)
            if not decision.is_noise:
                decision.is_noise = True
                decision.noise_score = max(decision.noise_score, 70)
                decision.recommended_action = "suppress"
                decision.reasons.append("already routed to noise bin")
            decisions.append(decision)
        return {"removed_count": len([item for item in decisions if item.is_noise]), "items": [item.to_dict() for item in sorted(decisions, key=lambda value: value.noise_score, reverse=True)]}
