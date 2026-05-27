from __future__ import annotations

import hashlib
import re
from urllib.parse import quote_plus

from backend.osint.adapters.base import BaseAdapter
from backend.osint.scoring.confidence import assess, evidence_grade
from backend.osint.types import AdapterResult, EntityInput, OSINTArtifact, RunContext, SourceReliability, utc_now

LEGAL = "Local deterministic enrichment and browser-assisted OSINT task generation. No credential, OTP, login, CAPTCHA, or private API probing."

def make_artifact(entity_type: str, label: str, value: str, source: str, confidence, relationship: str, data: dict, tags: list[str] | None = None) -> OSINTArtifact:
    return OSINTArtifact(
        type=entity_type,
        label=label,
        value=value,
        source=source,
        source_url=data.get("source_url"),
        fetched_at=utc_now(),
        confidence_score=confidence.score,
        confidence_reason=confidence.reason,
        evidence_grade=evidence_grade(confidence.score, confidence.source_reliability),
        raw_evidence_ref=None,
        relationship=relationship,
        tags=tags or [],
        data=data,
        legal_basis=LEGAL,
    )

class AliasVariantAdapter(BaseAdapter):
    id = "local.alias_variants"
    name = "Alias and Username Variants"
    description = "Generate local alias, handle, and username candidates from analyst-provided names. Candidate-only."
    input_types = ["person", "full_name", "alias", "name", "email"]
    output_types = ["alias", "username_candidate", "search_query"]

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        raw = entity.value.strip()
        base = raw.split("@", 1)[0] if "@" in raw else raw
        words = [part.lower() for part in re.split(r"[^A-Za-z0-9]+", base) if part]
        candidates: set[str] = set()
        if words:
            candidates.add("".join(words))
            candidates.add(".".join(words))
            candidates.add("_".join(words))
            if len(words) >= 2:
                candidates.add(words[0][0] + words[-1])
                candidates.add(words[0] + words[-1][0])
        conf = assess(direct=False, reliability=SourceReliability.DERIVED, fp_risk="high", reason="Local alias permutation only; must be corroborated before any identity claim.")
        artifacts = [make_artifact("username_candidate", f"Candidate username: {item}", item, self.id, conf, "HAS_USERNAME_CANDIDATE", {"graph_visibility": "candidate_bin", "artifact_class": "candidate", "derived_from": raw}, ["candidate", "needs_corroboration"]) for item in sorted(candidates) if item]
        query = f'"{raw}" public profile OR username OR bio'
        artifacts.append(make_artifact("collection_gap", "Browser-assisted public search query", query, self.id, conf, "HAS_NEXT_ACTION", {"query": query, "graph_visibility": "candidate_bin", "artifact_class": "candidate"}, ["browser_assisted"]))
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts)

class PublicSearchTaskAdapter(BaseAdapter):
    id = "local.public_search_queries"
    name = "Browser-Assisted Public Search Queries"
    description = "Create safe public search tasks for analyst review/import. Does not claim results."
    input_types = ["person", "full_name", "alias", "username", "organization", "company", "brand", "email", "phone", "domain", "url", "crypto_wallet", "wallet_address", "location", "address", "city", "coordinates", "place", "vehicle", "license_plate_public", "vin_public", "vessel", "aircraft", "asset_tag", "ioc", "hash", "malware_hash", "sha256", "md5", "image_asset", "screenshot", "avatar", "document", "pdf", "office_document"]
    output_types = ["search_query", "collection_gap"]

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        value = entity.value.strip()
        templates = [
            f'"{value}"',
            f'"{value}" site:github.com OR site:gitlab.com',
            f'"{value}" filetype:pdf OR filetype:doc OR filetype:xls',
            f'"{value}" official OR contact OR profile',
        ]
        conf = assess(direct=False, reliability=SourceReliability.DERIVED, fp_risk="medium", reason="Search query generation is a next action, not a finding.")
        artifacts = [make_artifact("collection_gap", f"Search task: {query[:72]}", query, self.id, conf, "HAS_BROWSER_ASSISTED_TASK", {"query": query, "url": "https://www.google.com/search?q=" + quote_plus(query), "graph_visibility": "candidate_bin", "artifact_class": "candidate"}, ["browser_assisted", "next_action"]) for query in templates]
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts)

class OrgDomainCandidateAdapter(BaseAdapter):
    id = "local.org_domain_candidates"
    name = "Organization Domain Candidates"
    description = "Generate candidate domains from organization/brand names. Candidate-only until evidence confirms ownership."
    input_types = ["organization", "company", "brand"]
    output_types = ["domain_candidate", "search_query"]

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        slug = re.sub(r"[^a-z0-9]", "", entity.value.lower())
        domains = [slug + tld for tld in [".com", ".org", ".net", ".co"]] if slug else []
        conf = assess(direct=False, reliability=SourceReliability.DERIVED, fp_risk="high", reason="Domain candidates are generated from a name and require public evidence of ownership.")
        artifacts = [make_artifact("profile_candidate", f"Candidate domain: {domain}", domain, self.id, conf, "HAS_DOMAIN_CANDIDATE", {"graph_visibility": "candidate_bin", "artifact_class": "candidate", "derived_from": entity.value}, ["candidate"]) for domain in domains]
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts)

class WalletValidationAdapter(BaseAdapter):
    id = "local.wallet_validation"
    name = "Wallet Format and Explorer Links"
    description = "Infer chain and create public explorer review tasks. Attribution requires evidence."
    input_types = ["crypto_wallet", "wallet_address", "tx_hash"]
    output_types = ["blockchain", "public_explorer_link", "external_link", "validation"]

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        value = entity.value.strip()
        chain = "ethereum" if re.fullmatch(r"0x[a-fA-F0-9]{40}", value) else "bitcoin" if re.fullmatch(r"(bc1|[13])[A-Za-z0-9]{25,62}", value) else "unknown"
        valid = chain != "unknown" or bool(re.fullmatch(r"0x[a-fA-F0-9]{64}", value))
        conf = assess(direct=True, reliability=SourceReliability.DERIVED, fp_risk="low" if valid else "high", reason="Local deterministic wallet/hash format validation; no attribution claim.")
        artifacts = [make_artifact("validation", f"Wallet format: {'valid' if valid else 'unknown'}", value, self.id, conf, "HAS_VALIDATION", {"valid": valid, "chain": chain})]
        if chain == "ethereum":
            artifacts.append(make_artifact("external_link", "Etherscan review task", f"https://etherscan.io/address/{value}", self.id, conf, "HAS_BROWSER_ASSISTED_TASK", {"source_url": f"https://etherscan.io/address/{value}", "graph_visibility": "candidate_bin", "artifact_class": "candidate"}, ["browser_assisted"]))
        if chain == "bitcoin":
            artifacts.append(make_artifact("external_link", "Mempool review task", f"https://mempool.space/address/{value}", self.id, conf, "HAS_BROWSER_ASSISTED_TASK", {"source_url": f"https://mempool.space/address/{value}", "graph_visibility": "candidate_bin", "artifact_class": "candidate"}, ["browser_assisted"]))
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=artifacts)

class IocClassifierAdapter(BaseAdapter):
    id = "local.ioc_classifier"
    name = "IOC Type Classifier"
    description = "Classify analyst-provided IOC strings locally."
    input_types = ["ioc", "hash", "malware_hash", "url", "domain", "ip"]
    output_types = ["validation", "search_query"]

    async def run(self, entity: EntityInput, context: RunContext) -> AdapterResult:
        value = entity.value.strip()
        kind = "sha256" if re.fullmatch(r"[a-fA-F0-9]{64}", value) else "md5" if re.fullmatch(r"[a-fA-F0-9]{32}", value) else "url" if value.startswith(("http://", "https://")) else "domain_or_ip"
        conf = assess(direct=True, reliability=SourceReliability.DERIVED, fp_risk="low", reason="Deterministic IOC shape classification only.")
        return AdapterResult(adapter_id=self.id, input=entity, artifacts=[make_artifact("validation", f"IOC type: {kind}", value, self.id, conf, "HAS_IOC_TYPE", {"ioc_type": kind})])
