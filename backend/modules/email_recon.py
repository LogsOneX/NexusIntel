from __future__ import annotations

import asyncio
import re
from typing import Any

from .common import AsyncHttpClient, EmitCallback, ReconFinding, maybe_emit, normalize_username
from .workspace_recon import WorkspaceResolver
from .identity_recon import IdentityResolver

EMAIL_RE = re.compile(r"^(?=.{6,254}$)[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
DISPOSABLE_DOMAINS = {
    "10minutemail.com", "guerrillamail.com", "mailinator.com", "tempmail.com", "temp-mail.org", "trashmail.com", "yopmail.com", "sharklasers.com", "getnada.com", "dispostable.com",
}


class EmailPresenceResolver:
    """Safe public email posture resolver.

    This intentionally avoids registration, password-reset, SMTP VRFY, SMTP RCPT, and contact-sync probes.
    It resolves public DNS/workspace posture, public avatar hashes, and local-part public username pivots.
    """

    def __init__(self, *, timeout: float = 10.0, identity_limit: int = 24):
        self.timeout = timeout
        self.identity_limit = identity_limit
        self.workspace = WorkspaceResolver(timeout=timeout)
        self.identity = IdentityResolver(concurrency=24, timeout=timeout)

    async def resolve(self, email: str, *, emit: EmitCallback | None = None) -> dict[str, Any]:
        target = email.strip().lower()
        valid = bool(EMAIL_RE.match(target))
        local, domain = target.rsplit("@", 1) if "@" in target else (target, "")
        findings: list[ReconFinding] = [
            ReconFinding("validation", "Email format", f"email:{target}:format", "ghost_email", "high" if valid else "low", "HAS_VALIDATION", {"valid": valid}),
        ]
        await maybe_emit(emit, f"Email syntax validation: {'valid' if valid else 'invalid'}", findings[-1].as_artifact())
        if domain:
            disposable = domain in DISPOSABLE_DOMAINS
            finding = ReconFinding("email_posture", "Disposable email domain", f"{domain}:disposable", "ghost_email", "high" if disposable else "medium", "HAS_EMAIL_POSTURE", {"domain": domain, "disposable": disposable})
            findings.append(finding)
            await maybe_emit(emit, f"Disposable domain check: {domain}={disposable}", finding.as_artifact())
        if local:
            username = normalize_username(local)
            local_finding = ReconFinding("username", username, username, "ghost_email", "medium", "HAS_LOCAL_PART", {"derived_from": target})
            findings.append(local_finding)
            await maybe_emit(emit, f"Derived username from email local-part: {username}", local_finding.as_artifact())
        workspace_result = await self.workspace.resolve(target, emit=emit)
        findings.extend(ReconFinding(**{k: artifact[k] for k in ["type", "label", "value", "source", "confidence", "relationship"]}, data=artifact.get("data") or {}) for artifact in workspace_result.get("artifacts", []))
        identity_result = {"artifacts": [], "checked": 0, "found": 0}
        if local and valid and self.identity_limit != 0:
            identity_result = await self.identity.resolve(local, emit=emit, limit=self.identity_limit)
            findings.extend(ReconFinding(**{k: artifact[k] for k in ["type", "label", "value", "source", "confidence", "relationship"]}, data=artifact.get("data") or {}) for artifact in identity_result.get("artifacts", []))
        guardrail = ReconFinding(
            "guardrail",
            "Unsafe email account-existence probes skipped",
            f"email:{target}:guardrail",
            "ghost_email",
            "confirmed",
            "HAS_GUARDRAIL",
            {"skipped": ["signup_pre_registration", "password_reset", "smtp_vrfy", "smtp_rcpt_to", "contact_sync"], "reason": "public-source-only policy"},
        )
        findings.append(guardrail)
        return {
            "target": target,
            "valid": valid,
            "domain": domain,
            "workspace": workspace_result,
            "identity_pivots": identity_result,
            "artifacts": [finding.as_artifact() for finding in findings],
        }
