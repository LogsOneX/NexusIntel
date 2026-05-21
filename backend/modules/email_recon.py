from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from .common import AsyncHttpClient, EmitCallback, ReconFinding, maybe_emit, normalize_username, public_metadata
from .identity_recon import IdentityResolver
from .workspace_recon import WorkspaceResolver

EMAIL_RE = re.compile(r"^(?=.{6,254}$)[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
DISPOSABLE_DOMAINS = {
    "10minutemail.com", "guerrillamail.com", "mailinator.com", "tempmail.com", "temp-mail.org", "trashmail.com", "yopmail.com", "sharklasers.com", "getnada.com", "dispostable.com",
}


@dataclass(frozen=True, slots=True)
class SignupSurface:
    name: str
    url: str
    marker_terms: tuple[str, ...]
    category: str = "signup_surface"


PUBLIC_SIGNUP_SURFACES: tuple[SignupSurface, ...] = (
    SignupSurface("GitHub", "https://github.com/signup", ("email", "password", "signup")),
    SignupSurface("GitLab", "https://gitlab.com/users/sign_up", ("email", "password", "sign up")),
    SignupSurface("Reddit", "https://www.reddit.com/register/", ("email", "username", "password")),
    SignupSurface("Medium", "https://medium.com/m/signin", ("email", "sign")),
    SignupSurface("DevTo", "https://dev.to/enter", ("email", "password")),
    SignupSurface("DockerHub", "https://hub.docker.com/signup", ("email", "username")),
    SignupSurface("npm", "https://www.npmjs.com/signup", ("email", "username")),
    SignupSurface("Replit", "https://replit.com/signup", ("email", "username")),
    SignupSurface("Kaggle", "https://www.kaggle.com/account/login", ("email", "username")),
    SignupSurface("HuggingFace", "https://huggingface.co/join", ("email", "username")),
    SignupSurface("SoundCloud", "https://soundcloud.com/signin", ("email", "sign")),
    SignupSurface("Spotify", "https://www.spotify.com/signup", ("email", "password")),
)


class PublicSignupSignatureAnalyzer:
    """GET-only public sign-up surface parser.

    The analyzer fetches unauthenticated public registration documents and extracts static response
    signatures. It never submits the target email, never triggers password reset, and never creates an
    account/session on behalf of the target.
    """

    def __init__(self, *, timeout: float = 10.0, concurrency: int = 10):
        self.timeout = timeout
        self.concurrency = concurrency

    async def inspect_surface(self, client: AsyncHttpClient, surface: SignupSurface) -> ReconFinding | None:
        result = await client.request_text("GET", surface.url, retries=1, max_bytes=220_000)
        status = int(result.get("status") or 0)
        text = str(result.get("text") or "")
        if status >= 400 or not text:
            return None
        lowered = text[:120_000].lower()
        matched = [term for term in surface.marker_terms if term.lower() in lowered]
        if not matched:
            return None
        parsed = public_metadata(text)
        host = urlparse(str(result.get("url") or surface.url)).netloc
        return ReconFinding(
            "signup_signature",
            f"{surface.name} public signup signature",
            surface.url,
            "ghost_email",
            "medium",
            "EXPOSES_PUBLIC_SIGNUP_SIGNATURE",
            {
                "platform": surface.name,
                "host": host,
                "status_code": status,
                "final_url": result.get("url"),
                "matched_public_terms": matched,
                "metadata": parsed,
                "target_email_submitted": False,
                "state_changing_request": False,
            },
        )

    async def resolve(self, *, emit: EmitCallback | None = None, limit: int | None = None) -> dict[str, Any]:
        surfaces = PUBLIC_SIGNUP_SURFACES[:limit] if limit is not None else PUBLIC_SIGNUP_SURFACES
        findings: list[ReconFinding] = []
        async with AsyncHttpClient(concurrency=self.concurrency, timeout=self.timeout) as client:
            for future in asyncio.as_completed([self.inspect_surface(client, surface) for surface in surfaces]):
                finding = await future
                if finding:
                    findings.append(finding)
                    await maybe_emit(emit, f"Public signup response signature parsed: {finding.label}", finding.as_artifact())
        return {"checked": len(surfaces), "found": len(findings), "artifacts": [finding.as_artifact() for finding in findings]}


class EmailPresenceResolver:
    """Public email posture resolver.

    It resolves syntax, domain/workspace posture, public avatar hash, GET-only signup surface metadata,
    and local-part username pivots. It does not send target emails, submit registration forms, trigger
    password resets, or perform SMTP VRFY/RCPT probes.
    """

    def __init__(self, *, timeout: float = 10.0, identity_limit: int = 24, signup_limit: int | None = None):
        self.timeout = timeout
        self.identity_limit = identity_limit
        self.signup_limit = signup_limit
        self.workspace = WorkspaceResolver(timeout=timeout)
        self.identity = IdentityResolver(concurrency=24, timeout=timeout)
        self.signup = PublicSignupSignatureAnalyzer(timeout=timeout)

    @staticmethod
    def artifact_to_finding(artifact: dict[str, Any]) -> ReconFinding:
        return ReconFinding(
            type=str(artifact.get("type") or "signal"),
            label=str(artifact.get("label") or artifact.get("value") or "signal"),
            value=str(artifact.get("value") or artifact.get("label") or "signal"),
            source=str(artifact.get("source") or "ghost_email"),
            confidence=str(artifact.get("confidence") or "medium"),
            relationship=str(artifact.get("relationship") or "DERIVED_SIGNAL"),
            data=dict(artifact.get("data") or {}),
        )

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

        workspace_result, signup_result = await asyncio.gather(
            self.workspace.resolve(target, emit=emit),
            self.signup.resolve(emit=emit, limit=self.signup_limit),
        )
        findings.extend(self.artifact_to_finding(artifact) for artifact in workspace_result.get("artifacts", []))
        findings.extend(self.artifact_to_finding(artifact) for artifact in signup_result.get("artifacts", []))

        identity_result = {"artifacts": [], "checked": 0, "found": 0}
        if local and valid and self.identity_limit != 0:
            identity_result = await self.identity.resolve(local, emit=emit, limit=self.identity_limit)
            findings.extend(self.artifact_to_finding(artifact) for artifact in identity_result.get("artifacts", []))

        guardrail = ReconFinding(
            "guardrail",
            "Read-only email analysis boundary",
            f"email:{target}:guardrail",
            "ghost_email",
            "confirmed",
            "HAS_GUARDRAIL",
            {
                "allowed": ["dns_workspace_posture", "public_avatar_hash", "public_signup_document_get", "local_part_username_pivot"],
                "skipped": ["password_reset", "otp_trigger", "account_creation", "smtp_vrfy", "smtp_rcpt_to", "contact_sync"],
                "target_email_submitted_to_signup_forms": False,
            },
        )
        findings.append(guardrail)
        return {
            "target": target,
            "valid": valid,
            "domain": domain,
            "workspace": workspace_result,
            "signup_signatures": signup_result,
            "identity_pivots": identity_result,
            "artifacts": [finding.as_artifact() for finding in findings],
        }
