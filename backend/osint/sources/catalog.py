from __future__ import annotations

from dataclasses import asdict, dataclass

from backend.osint.sources.modes import SourceMode

@dataclass(frozen=True, slots=True)
class SourceCapability:
    id: str
    name: str
    row: str
    source_mode: SourceMode
    cost_profile: str
    requires_api_key: bool
    requires_browser: bool
    passive: bool
    input_types: list[str]
    output_types: list[str]
    evidence_behavior: str
    noise_risk: str
    legal_note: str
    enabled: bool = True
    disabled_reason: str | None = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["source_mode"] = self.source_mode.value
        return data

_SOURCE_CAPABILITIES = [
    SourceCapability('local.entity_normalization', 'Entity Normalization', 'Person', SourceMode.LOCAL_NATIVE, 'local/free', False, False, True, ['person', 'username', 'email', 'phone', 'domain', 'wallet_address'], ['normalized_entity', 'validation'], 'local deterministic normalization; no external source', 'low', 'Runs locally; no collection beyond analyst-provided input.', True, None),
    SourceCapability('local.alias_permutation', 'Alias & Username Candidate Generator', 'Username', SourceMode.LOCAL_NATIVE, 'local/free', False, False, True, ['person', 'full_name', 'alias', 'email'], ['alias', 'username_candidate', 'search_query'], 'candidate-only derived pivots; no identity confirmation', 'medium', 'Candidates must be corroborated before reporting.', True, None),
    SourceCapability('public.dns', 'Public DNS Resolver', 'Domain', SourceMode.PUBLIC_PASSIVE, 'free', False, False, True, ['domain', 'subdomain', 'email'], ['dns_record', 'mx_record', 'txt_record', 'ip'], 'captures DNS answer payloads as evidence', 'low', 'Passive DNS resolution only.', True, None),
    SourceCapability('public.rdap', 'Public RDAP', 'IP', SourceMode.PUBLIC_PASSIVE, 'free', False, False, True, ['domain', 'ip'], ['rdap_record', 'asn', 'registrar'], 'captures RDAP JSON evidence', 'low', 'Public registration/allocation metadata only.', True, None),
    SourceCapability('public.crtsh', 'crt.sh Certificate Transparency', 'Threat IOC', SourceMode.PUBLIC_PASSIVE, 'free', False, False, True, ['domain'], ['subdomain', 'certificate'], 'captures CT records where available', 'medium', 'CT names are pivots, not attribution.', True, None),
    SourceCapability('browser.search_tasks', 'Browser-Assisted Search Tasks', 'Person', SourceMode.BROWSER_ASSISTED, 'manual/free', False, True, True, ['person', 'organization', 'email', 'phone', 'wallet_address', 'vehicle', 'ioc'], ['search_query', 'collection_gap'], 'creates analyst tasks; analyst imports evidence manually', 'medium', 'No scraping behind auth; analyst controls browser review.', True, None),
    SourceCapability('import.spiderfoot', 'SpiderFoot Import', 'Importers', SourceMode.IMPORTED_EVIDENCE, 'local/free', False, False, True, ['file'], ['ioc', 'domain', 'ip', 'email', 'evidence'], 'stores imported rows as analyst evidence', 'medium', 'Imported data remains candidate until confirmed.', True, None),
    SourceCapability('import.maltego', 'Maltego CSV Import', 'Importers', SourceMode.IMPORTED_EVIDENCE, 'local/free', False, False, True, ['file'], ['entity', 'relationship', 'evidence'], 'stores imported mapping as evidence', 'medium', 'Analyst-provided export; preserve source note.', True, None),
    SourceCapability('import.tool_json', 'Open Tool JSON Import', 'Importers', SourceMode.IMPORTED_EVIDENCE, 'local/free', False, False, True, ['file'], ['evidence', 'candidate_lead'], 'supports GHunt/Holehe/Maigret/Sherlock/URLScan/Shodan-style JSON exports', 'medium', 'No claims without source/citation from imported output.', True, None),
    SourceCapability('local.image', 'Local Image Intelligence', 'Image', SourceMode.LOCAL_NATIVE, 'local/free', False, False, True, ['image_asset', 'screenshot'], ['image_hash', 'exif_metadata', 'ocr_text', 'visual_match_candidate'], 'local file metadata/hashes; OCR optional', 'low', 'Reverse search is browser-assisted unless analyst imports evidence.', True, None),
    SourceCapability('local.document', 'Local Document Intelligence', 'Document', SourceMode.LOCAL_NATIVE, 'local/free', False, False, True, ['document', 'pdf', 'office_document'], ['hash', 'ocr_text', 'embedded_link', 'embedded_email', 'timeline_event'], 'local metadata/text/entity extraction', 'low', 'Document contents are analyst-provided evidence.', True, None),
    SourceCapability('local.crypto', 'Local Crypto Wallet Intelligence', 'Crypto', SourceMode.LOCAL_NATIVE, 'local/free', False, False, True, ['crypto_wallet', 'wallet_address', 'tx_hash'], ['blockchain', 'public_explorer_link', 'wallet_cluster'], 'validates address and creates explorer/import tasks', 'medium', 'Wallet attribution requires external evidence.', True, None),
    SourceCapability('optional.github', 'GitHub Public Search', 'Username', SourceMode.OPTIONAL_BYOK, 'byok', True, False, True, ['email', 'username'], ['public_code_hit', 'public_profile'], 'official API evidence when key configured', 'low', 'Official GitHub API/BYOK only.', False, 'missing_api_key'),
    SourceCapability('optional.urlscan', 'URLScan Connector', 'Threat IOC', SourceMode.OPTIONAL_BYOK, 'byok', True, False, True, ['domain', 'url'], ['urlscan_result'], 'official API evidence when adapter implemented', 'medium', 'Disabled until adapter is implemented and key configured.', False, 'adapter_not_implemented'),
    SourceCapability('local.email_syntax', 'Email Syntax and Domain Split', 'Email', SourceMode.LOCAL_NATIVE, 'local/free', False, False, True, ['email'], ['validation', 'domain', 'email_local_part'], 'derived from analyst-provided input; no account existence claim', 'low', 'No registration, OTP, or password-reset probing.', True, None),
    SourceCapability('public.email_dns', 'Email Workspace DNS', 'Email', SourceMode.PUBLIC_PASSIVE, 'free', False, False, True, ['email'], ['domain', 'mx_record', 'txt_record', 'workspace_signal'], 'captures public DNS answers as evidence', 'low', 'Passive DNS only; no mailbox probing.', True, None),
    SourceCapability('local.phone_numbering', 'Phone Numbering Plan', 'Phone', SourceMode.LOCAL_NATIVE, 'local/free', False, False, True, ['phone'], ['phone_posture', 'validation'], 'local/metadata validation, no contact-sync or OTP', 'low', 'No messenger registration or OTP claims.', True, None),
    SourceCapability('browser.org_registry', 'Organization Registry Search Tasks', 'Organization', SourceMode.BROWSER_ASSISTED, 'manual/free', False, True, True, ['organization', 'company', 'brand'], ['search_query', 'collection_gap'], 'analyst imports registry evidence manually', 'medium', 'Ownership claims require official/public evidence.', True, None),
    SourceCapability('public.url_metadata', 'URL Public Metadata', 'URL', SourceMode.PUBLIC_PASSIVE, 'free', False, False, True, ['url'], ['web_fingerprint', 'external_link'], 'captures public page metadata where reachable', 'medium', 'No authenticated pages or private API abuse.', True, None),
    SourceCapability('browser.location_review', 'Location and Maps Review Tasks', 'Location', SourceMode.BROWSER_ASSISTED, 'manual/free', False, True, True, ['location', 'address', 'coordinates', 'google_maps_profile'], ['search_query', 'google_maps_review'], 'analyst imports public map/source evidence', 'medium', 'No automated scraping behind auth.', True, None),
    SourceCapability('browser.vehicle_mentions', 'Vehicle/Asset Public Mention Tasks', 'Vehicle', SourceMode.BROWSER_ASSISTED, 'manual/free', False, True, True, ['vehicle', 'license_plate_public', 'vin_public', 'vessel', 'aircraft'], ['search_query', 'public_registration_candidate'], 'browser-assisted public-source tasks', 'medium', 'No restricted database access.', True, None),
    SourceCapability('report.local_builder', 'Evidence-First Report Builder', 'Reports', SourceMode.LOCAL_NATIVE, 'local/free', False, False, True, ['investigation'], ['pdf', 'html', 'json', 'csv'], 'uses only case graph/evidence/citations', 'low', 'Unsupported claims are marked insufficient evidence.', True, None),
    SourceCapability('ai.rules_investigator', 'Rules-Only Investigator', 'Local AI', SourceMode.LOCAL_NATIVE, 'local/free', False, False, True, ['investigation', 'evidence'], ['facts', 'hypotheses', 'next_actions'], 'local rules and optional local model summaries cite evidence', 'low', 'AI cannot upgrade confidence without evidence.', True, None),
]

MATRIX_ROWS = ["Person", "Username", "Email", "Phone", "Organization", "Domain", "IP", "URL", "Image", "Document", "Location", "Crypto", "Vehicle", "Threat IOC", "Importers", "Reports", "Local AI"]
MATRIX_COLUMNS = [mode.value for mode in SourceMode]

def source_catalog() -> list[dict]:
    return [item.to_dict() for item in _SOURCE_CAPABILITIES]

def source_capability_matrix() -> dict:
    matrix = {row: {column: [] for column in MATRIX_COLUMNS} for row in MATRIX_ROWS}
    for item in _SOURCE_CAPABILITIES:
        matrix.setdefault(item.row, {column: [] for column in MATRIX_COLUMNS})
        matrix[item.row].setdefault(item.source_mode.value, []).append(item.to_dict())
    return {"rows": MATRIX_ROWS, "columns": MATRIX_COLUMNS, "matrix": matrix}
