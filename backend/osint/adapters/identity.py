from __future__ import annotations

from backend.modules.identity_recon import IdentityResolver
from backend.osint.adapters.base import BaseAdapter
from backend.osint.scoring.confidence import assess, evidence_grade
from backend.osint.types import AdapterResult, EntityInput, OSINTArtifact, RawEvidenceObject, RunContext, SourceReliability, utc_now

LEGAL = "Passive public profile HTTP GET checks only; no login, contact sync, or private API."


class UsernameProfilesAdapter(BaseAdapter):
    id = "username.public_profiles"
    name = "Username Public Profiles"
    description = "Resolve username presence across curated public profile surfaces."
    input_types = ["username"]
    output_types = ["public_profile", "platform", "external_link", "avatar"]
    rate_limit = BaseAdapter.rate_limit

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        username = entity.value.strip().lstrip("@")
        resolver = IdentityResolver(concurrency=16, timeout=10)
        result = await resolver.resolve(username, limit=int(context.options.get("limit", 40) or 40))
        artifacts = []
        raw_evidence = []
        for row in result.get("artifacts", []):
            data = dict(row.get("data") or {})
            url = str(row.get("value") or data.get("url") or "")
            confidence_text = str(row.get("confidence") or "medium")
            score = 82 if confidence_text in {"high", "confirmed"} else 65 if confidence_text == "medium" else 42
            conf = assess(direct=True, reliability=SourceReliability.PUBLIC_WEB, fp_risk="medium" if score >= 60 else "high", reason="Public profile surface matched username markers and false-positive heuristics.")
            artifacts.append(OSINTArtifact(type="public_profile", label=str(row.get("label") or url), value=url or str(row.get("label")), source=self.id, source_url=url or None, fetched_at=utc_now(), confidence_score=score, confidence_reason=conf.reason, evidence_grade=evidence_grade(score, conf.source_reliability), raw_evidence_ref=None, relationship="OBSERVED_ON", tags=[str(data.get("category") or "profile")], data=data, legal_basis=LEGAL))
            if data:
                raw_evidence.append(RawEvidenceObject(source=self.id, source_url=url or None, payload=data, content_type="application/json"))
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts, raw_evidence=raw_evidence)
