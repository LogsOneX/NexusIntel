from __future__ import annotations

from backend.modules.phone_recon import PhoneResolver
from backend.osint.adapters.base import BaseAdapter
from backend.osint.scoring.confidence import assess, evidence_grade
from backend.osint.types import AdapterResult, EntityInput, OSINTArtifact, RawEvidenceObject, RunContext, SourceReliability, utc_now

LEGAL = "Public numbering-plan metadata and public deeplink metadata only; no contact-sync or registration claims."


class PhoneNumberingPlanAdapter(BaseAdapter):
    id = "phone.numbering_plan"
    name = "Phone Numbering Plan"
    description = "Validate E.164 and extract public numbering-plan metadata."
    input_types = ["phone"]
    output_types = ["phone_posture", "country_code", "carrier_hint"]

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        resolver = PhoneResolver(timeout=8)
        result = await resolver.resolve(entity.value.strip())
        conf = assess(direct=True, reliability=SourceReliability.PRIMARY, fp_risk="low", reason="Public numbering plan/phonenumbers metadata; not an account registration claim.")
        artifacts = [OSINTArtifact(type="phone_posture", label=f"Phone posture {entity.value}", value=entity.value.strip(), source=self.id, source_url=None, fetched_at=utc_now(), confidence_score=conf.score, confidence_reason=conf.reason, evidence_grade=evidence_grade(conf.score, conf.source_reliability), raw_evidence_ref=None, relationship="HAS_PHONE_POSTURE", tags=["numbering_plan"], data=result, legal_basis=LEGAL)]
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts, raw_evidence=[RawEvidenceObject(source=self.id, source_url=None, payload=result, content_type="application/json")])
