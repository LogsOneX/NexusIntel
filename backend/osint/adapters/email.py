from __future__ import annotations

import hashlib
import re
from urllib.parse import quote

import dns.resolver
import httpx

from backend.osint.adapters.base import BaseAdapter
from backend.osint.scoring.confidence import assess, evidence_grade
from backend.osint.types import AdapterResult, EntityInput, OSINTArtifact, RawEvidenceObject, RunContext, SourceReliability, utc_now

EMAIL_RE = re.compile(r"^(?=.{6,254}$)[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
LEGAL = "Passive public-source or official API/BYOK collection; no signup/password-reset/contact-sync probing."


def artifact(entity_type: str, label: str, value: str, source: str, source_url: str | None, confidence, relationship: str, data: dict, tags: list[str] | None = None, raw_ref: str | None = None) -> OSINTArtifact:
    return OSINTArtifact(
        type=entity_type, label=label, value=value, source=source, source_url=source_url, fetched_at=utc_now(),
        confidence_score=confidence.score, confidence_reason=confidence.reason, evidence_grade=evidence_grade(confidence.score, confidence.source_reliability),
        raw_evidence_ref=raw_ref, relationship=relationship, tags=tags or [], data=data, legal_basis=LEGAL,
    )


class EmailSyntaxAdapter(BaseAdapter):
    id = "email.syntax"
    name = "Email Syntax"
    description = "Validate email syntax and split local/domain parts."
    input_types = ["email"]
    output_types = ["email_local_part", "domain", "validation"]

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        email = entity.value.strip().lower()
        valid = bool(EMAIL_RE.match(email))
        local, domain = email.rsplit("@", 1) if "@" in email else (email, "")
        conf = assess(direct=True, reliability=SourceReliability.DERIVED, fp_risk="low", reason="Deterministic RFC-style syntax parsing; not an account-existence claim.")
        artifacts = [artifact("validation", f"Email syntax: {'valid' if valid else 'invalid'}", f"email:{email}:syntax", self.id, None, conf, "HAS_VALIDATION", {"valid": valid, "email": email})]
        if local:
            artifacts.append(artifact("email_local_part", local, local, self.id, None, conf, "HAS_LOCAL_PART", {"derived_from": email}, ["candidate"]))
        if domain:
            artifacts.append(artifact("domain", domain, domain, self.id, None, conf, "HAS_DOMAIN", {"derived_from": email}))
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts)


class EmailDomainWorkspaceAdapter(BaseAdapter):
    id = "email.domain_workspace"
    name = "Email Domain Workspace"
    description = "Collect MX/TXT workspace posture for the email domain."
    input_types = ["email"]
    output_types = ["domain", "mx_record", "txt_record", "workspace_signal"]

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        email = entity.value.strip().lower()
        if "@" not in email:
            return AdapterResult(adapter_id=self.id, input=entity, warnings=["Invalid email; no domain"], status="skipped")
        domain = email.rsplit("@", 1)[1]
        evidence_payload: dict[str, list[str]] = {"MX": [], "TXT": []}
        warnings: list[str] = []
        for rtype in ["MX", "TXT"]:
            try:
                answers = dns.resolver.resolve(domain, rtype, lifetime=5)
                for answer in answers:
                    if rtype == "MX":
                        evidence_payload[rtype].append(str(answer.exchange).rstrip("."))
                    else:
                        strings = getattr(answer, "strings", None)
                        evidence_payload[rtype].append("".join(part.decode("utf-8", "ignore") for part in strings) if strings else str(answer).strip('"'))
            except Exception as exc:
                warnings.append(f"DNS {rtype} lookup failed for {domain}: {exc.__class__.__name__}")
        raw = RawEvidenceObject(source=self.id, source_url=f"dns:{domain}", payload=evidence_payload, content_type="application/json")
        has_records = bool(evidence_payload["MX"] or evidence_payload["TXT"])
        conf = assess(direct=has_records, reliability=SourceReliability.PRIMARY, fp_risk="low" if has_records else "high", reason="DNS records resolved directly from public DNS." if has_records else "Public DNS returned no MX/TXT records or timed out; weak domain posture only.")
        artifacts = [artifact("domain", domain, domain, self.id, f"dns:{domain}", conf, "HAS_DOMAIN", {"email": email})]
        for mx in sorted(set(evidence_payload["MX"])):
            artifacts.append(artifact("mx_record", mx, mx, self.id, f"dns:{domain}", conf, "HAS_MX", {"domain": domain}))
        for txt in sorted(set(evidence_payload["TXT"]))[:20]:
            artifacts.append(artifact("txt_record", txt[:96], txt, self.id, f"dns:{domain}", conf, "HAS_TXT", {"domain": domain}))
        providers = []
        joined = " ".join(evidence_payload["MX"] + evidence_payload["TXT"]).lower()
        for name, marker in {"Google Workspace": "google", "Microsoft 365": "outlook", "Proton": "proton", "Zoho": "zoho"}.items():
            if marker in joined:
                providers.append(name)
                artifacts.append(artifact("workspace_signal", name, f"{domain}:{name}", self.id, f"dns:{domain}", conf, "USES_WORKSPACE", {"domain": domain, "provider": name}))
        if not has_records:
            warnings.append(f"No MX/TXT records observed for {domain}; workspace signal unavailable")
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts, raw_evidence=[raw], warnings=warnings)


class GravatarAdapter(BaseAdapter):
    id = "email.gravatar"
    name = "Gravatar Public Avatar"
    description = "Check public Gravatar avatar/profile endpoints by MD5 lowercase email hash."
    input_types = ["email"]
    output_types = ["avatar", "avatar_hash", "public_profile"]

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        email = entity.value.strip().lower()
        digest = hashlib.md5(email.encode("utf-8")).hexdigest()
        avatar_url = f"https://www.gravatar.com/avatar/{digest}?d=404"
        artifacts = []
        raw_evidence = []
        try:
            async with httpx.AsyncClient(timeout=10, follow_redirects=False, headers={"User-Agent": "NexusIntel/2.3 public-osint"}) as client:
                response = await client.get(avatar_url)
                raw_evidence.append(RawEvidenceObject(source=self.id, source_url=avatar_url, payload={"status_code": response.status_code, "headers": dict(response.headers)}, content_type="application/json", headers=dict(response.headers)))
                conf = assess(direct=response.status_code == 200, reliability=SourceReliability.PUBLIC_WEB, fp_risk="low" if response.status_code == 200 else "high", reason="Public Gravatar avatar endpoint returned HTTP status for the normalized email hash.")
                artifacts.append(artifact("avatar_hash", digest, digest, self.id, avatar_url, conf, "HAS_GRAVATAR_HASH", {"email_hash_md5": digest, "status_code": response.status_code}))
                if response.status_code == 200:
                    artifacts.append(artifact("avatar", f"Gravatar avatar {digest[:8]}", avatar_url, self.id, avatar_url, conf, "HAS_AVATAR", {"email_hash_md5": digest}))
                profile_url = f"https://gravatar.com/{digest}.json"
                profile_response = await client.get(profile_url)
                raw_evidence.append(RawEvidenceObject(source=self.id, source_url=profile_url, payload={"status_code": profile_response.status_code, "body": profile_response.text[:200000]}, content_type="application/json", headers=dict(profile_response.headers)))
                if profile_response.status_code == 200:
                    artifacts.append(artifact("public_profile", "Gravatar public profile", profile_url, self.id, profile_url, conf, "HAS_PUBLIC_PROFILE", {"email_hash_md5": digest}))
        except httpx.HTTPError as exc:
            conf = assess(direct=False, reliability=SourceReliability.PUBLIC_WEB, fp_risk="high", reason="Gravatar endpoint could not be reached; hash retained as weak derived pivot only.")
            artifacts.append(artifact("avatar_hash", digest, digest, self.id, avatar_url, conf, "HAS_GRAVATAR_HASH", {"email_hash_md5": digest, "warning": str(exc)}))
            return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts, raw_evidence=raw_evidence, warnings=[f"Gravatar request failed: {exc.__class__.__name__}"])
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts, raw_evidence=raw_evidence)


class GitHubPublicSearchAdapter(BaseAdapter):
    id = "email.github_public_search"
    name = "GitHub Public Search"
    description = "Search public GitHub code/issues/users for exact email with GITHUB_TOKEN."
    input_types = ["email"]
    output_types = ["public_code_hit", "public_profile"]
    requires_api_key = True

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        token = context.api_keys.get("github") or context.api_keys.get("GITHUB_TOKEN")
        if not token:
            return AdapterResult(adapter_id=self.id, input=entity, warnings=["GITHUB_TOKEN not configured"], status="disabled")
        email = entity.value.strip().lower()
        url = f"https://api.github.com/search/code?q={quote(email)}"
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "NexusIntel/2.3 public-osint"}
        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            response = await client.get(url)
            raw = RawEvidenceObject(source=self.id, source_url=url, payload={"status_code": response.status_code, "body": response.text[:300000]}, content_type="application/json", headers=dict(response.headers))
            response.raise_for_status()
            data = response.json()
        conf = assess(direct=True, reliability=SourceReliability.OFFICIAL_API, fp_risk="low", reason="Official GitHub API public search for exact email string.")
        artifacts = []
        for item in data.get("items", [])[:10]:
            html_url = item.get("html_url")
            if html_url:
                artifacts.append(artifact("public_code_hit", item.get("name") or html_url, html_url, self.id, html_url, conf, "MENTIONED_IN_PUBLIC_CODE", {"repository": item.get("repository", {})}))
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts, raw_evidence=[raw])


class HIBPAdapter(BaseAdapter):
    id = "email.hibp"
    name = "Have I Been Pwned BYOK"
    description = "Query official HIBP breachedaccount API only with HIBP_API_KEY."
    input_types = ["email"]
    output_types = ["breach_record"]
    requires_api_key = True

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        key = context.api_keys.get("hibp") or context.api_keys.get("HIBP_API_KEY")
        if not key:
            return AdapterResult(adapter_id=self.id, input=entity, warnings=["HIBP_API_KEY not configured"], status="disabled")
        email = entity.value.strip().lower()
        url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{quote(email)}?truncateResponse=false"
        headers = {"hibp-api-key": key, "User-Agent": "NexusIntel/2.3 analyst-byok"}
        async with httpx.AsyncClient(timeout=20, headers=headers) as client:
            response = await client.get(url)
            raw = RawEvidenceObject(source=self.id, source_url=url, payload={"status_code": response.status_code, "body": response.text[:300000]}, content_type="application/json", headers={"status_code": response.status_code})
            if response.status_code == 404:
                return AdapterResult(adapter_id=self.id, input=entity, raw_evidence=[raw], warnings=["No HIBP breach records returned"], status="completed")
            response.raise_for_status()
            data = response.json()
        conf = assess(direct=True, reliability=SourceReliability.OFFICIAL_API, fp_risk="low", reason="Official HIBP API result for exact email, BYOK.")
        artifacts = [artifact("breach_record", row.get("Name") or row.get("Title") or "HIBP breach", str(row.get("Name") or row.get("Title") or "hibp"), self.id, url, conf, "HAS_BREACH_RECORD", row) for row in data[:20] if isinstance(row, dict)]
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts, raw_evidence=[raw])


class UsernameCandidateAdapter(BaseAdapter):
    id = "email.username_candidates"
    name = "Username Candidates"
    description = "Generate low-confidence username candidates from email local-part."
    input_types = ["email"]
    output_types = ["username_candidate"]

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        email = entity.value.strip().lower()
        local = email.split("@", 1)[0]
        base = re.sub(r"[^a-z0-9._-]", "", local)
        candidates = {base, base.replace(".", ""), base.replace("_", ""), base.replace("-", "")}
        if "." in base:
            parts = [part for part in re.split(r"[._-]+", base) if part]
            if len(parts) >= 2:
                candidates.add(parts[0] + parts[-1])
                candidates.add(parts[0][0] + parts[-1])
        conf = assess(direct=False, reliability=SourceReliability.DERIVED, fp_risk="high", reason="Local-part username candidate; requires corroboration before attribution.")
        artifacts = [artifact("username_candidate", f"Candidate username: {item}", item, self.id, None, conf, "HAS_USERNAME_CANDIDATE", {"derived_from": email, "graph_visibility": "candidate_bin", "artifact_class": "candidate"}, ["candidate", "needs_corroboration"]) for item in sorted(candidates) if item]
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts)
