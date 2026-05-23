from __future__ import annotations

from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from backend.modules.google_recon import _extract_reviews_from_html, _gaia_from_url, _metadata
from backend.osint.adapters.base import BaseAdapter
from backend.osint.scoring.confidence import assess, evidence_grade
from backend.osint.types import AdapterResult, EntityInput, OSINTArtifact, RawEvidenceObject, RunContext, SourceReliability, utc_now

LEGAL = "Analyst-supplied public Google Maps URL or public HTML only; no private/internal Google APIs."


class MapsProfileReviewsAdapter(BaseAdapter):
    id = "maps.profile_reviews"
    name = "Google Maps Public Profile Reviews"
    description = "Parse analyst-supplied public Google Maps contribution URL for visible review/photo/place metadata."
    input_types = ["google_maps_profile", "url"]
    output_types = ["google_maps_profile", "google_maps_review", "google_maps_place", "avatar", "gaia_id"]

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        url = entity.value.strip()
        if "google." not in url or "/maps" not in url:
            return AdapterResult(adapter_id=self.id, input=entity, warnings=["Input is not a public Google Maps URL"], status="skipped")
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers={"User-Agent": "NexusIntel/2.3 public-osint"}) as client:
            response = await client.get(url)
            response.raise_for_status()
            html = response.text[:500000]
        final_url = str(response.url)
        meta = _metadata(html)
        gaia = _gaia_from_url(final_url) or _gaia_from_url(url)
        reviews = _extract_reviews_from_html(html)
        soup = BeautifulSoup(html, "html.parser")
        image_urls = []
        for img in soup.find_all("img", src=True)[:30]:
            src = str(img.get("src"))
            if src.startswith("http") and src not in image_urls:
                image_urls.append(src)
        conf = assess(direct=True, reliability=SourceReliability.PUBLIC_WEB, fp_risk="low", reason="Analyst supplied public Google Maps document fetched directly.")
        artifacts = [OSINTArtifact(type="google_maps_profile", label=meta.get("og_title") or meta.get("title") or "Google Maps profile", value=final_url, source=self.id, source_url=final_url, fetched_at=utc_now(), confidence_score=conf.score, confidence_reason=conf.reason, evidence_grade=evidence_grade(conf.score, conf.source_reliability), raw_evidence_ref=None, relationship="HAS_MAPS_PROFILE", tags=["public_maps"], data={"gaia_id": gaia, "title": meta.get("title")}, legal_basis=LEGAL)]
        if gaia:
            artifacts.append(OSINTArtifact(type="gaia_id", label=gaia, value=gaia, source=self.id, source_url=final_url, fetched_at=utc_now(), confidence_score=conf.score, confidence_reason=conf.reason, evidence_grade=evidence_grade(conf.score, conf.source_reliability), raw_evidence_ref=None, relationship="HAS_GAIA_ID", tags=["public_url"], data={}, legal_basis=LEGAL))
        if meta.get("avatar_url"):
            artifacts.append(OSINTArtifact(type="avatar", label="Google public avatar", value=meta["avatar_url"], source=self.id, source_url=final_url, fetched_at=utc_now(), confidence_score=conf.score, confidence_reason=conf.reason, evidence_grade=evidence_grade(conf.score, conf.source_reliability), raw_evidence_ref=None, relationship="HAS_AVATAR", tags=["public_maps"], data={}, legal_basis=LEGAL))
        for i, review in enumerate(reviews):
            place = str(review.get("place_name") or f"review-{i}")
            artifacts.append(OSINTArtifact(type="google_maps_review", label=place[:96], value=f"{final_url}#review-{i}", source=self.id, source_url=final_url, fetched_at=utc_now(), confidence_score=conf.score, confidence_reason=conf.reason, evidence_grade=evidence_grade(conf.score, conf.source_reliability), raw_evidence_ref=None, relationship="POSTED", tags=["review"], data=review, legal_basis=LEGAL))
            artifacts.append(OSINTArtifact(type="google_maps_place", label=place[:96], value=place, source=self.id, source_url=final_url, fetched_at=utc_now(), confidence_score=conf.score, confidence_reason=conf.reason, evidence_grade=evidence_grade(conf.score, conf.source_reliability), raw_evidence_ref=None, relationship="REVIEWED_AT", tags=["place"], data={"place_name": place}, legal_basis=LEGAL))
        for i, image_url in enumerate(image_urls[:10]):
            artifacts.append(OSINTArtifact(type="google_maps_photo", label=f"Maps image {i+1}", value=image_url, source=self.id, source_url=final_url, fetched_at=utc_now(), confidence_score=70, confidence_reason="Image URL visible in public Maps HTML; review manually before attribution.", evidence_grade="B", raw_evidence_ref=None, relationship="HAS_PUBLIC_IMAGE", tags=["candidate"], data={}, legal_basis=LEGAL))
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts, raw_evidence=[RawEvidenceObject(source=self.id, source_url=final_url, payload={"status_code": response.status_code, "headers": dict(response.headers), "body": html}, content_type="text/html", headers=dict(response.headers))])
