from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

ArtifactClass = Literal["ENTITY", "EVIDENCE", "SIGNAL", "CANDIDATE", "COMPLIANCE", "NOISE"]
GraphVisibility = Literal["main_graph", "evidence_only", "signal_badge", "candidate_bin", "compliance_log", "noise_bin"]

ENTITY_TYPES = {
    "email", "username", "person_alias", "name", "domain", "url", "ip", "phone", "profile",
    "organization", "location", "place", "google_maps_profile", "google_maps_review", "google_maps_photo",
    "crypto_wallet", "crypto_transaction", "image_asset", "avatar", "favicon", "document",
    "infrastructure", "account", "service", "technology", "breach_record", "google_profile", "gaia_id",
}

EVIDENCE_TYPES = {
    "raw_html", "raw_json", "screenshot", "source_url", "http_response", "dns_record",
    "rdap_record", "certificate", "file_hash", "exif_metadata", "raw_text", "raw_evidence",
}

SIGNAL_TYPES = {
    "signal", "validation", "validation_signal", "risk", "network", "geoip", "registration",
    "phone_posture", "mx_posture", "disposable_email_hint", "mail_security", "provider_hint",
    "line_type_hint", "geoip_hint", "technology_hint", "suspicious_domain_indicator",
    "favicon_hash", "avatar_hash", "dns_posture", "workspace_posture", "mail_posture",
}

CANDIDATE_TYPES = {
    "profile_candidate", "candidate_profile", "candidate_url_only", "username_candidate",
    "email_candidate", "phone_deeplink_candidate", "possible_same_actor", "possible_profile",
}

COMPLIANCE_TYPES = {
    "guardrail", "skipped_check", "legal_note", "policy", "compliance",
    "blocked_transform", "prohibited_probe_notice",
}

NOISE_TYPES = {
    "generic_page", "generic_pages", "generic_login_page", "auth_wall", "auth_wall_only",
    "soft_404", "parked_domain", "false_positive_profile", "cdn_noise", "shared_hosting_noise",
    "registrar_privacy_noise", "generic_messenger_landing", "low_value_phone_deeplink",
}

GRAPH_VISIBILITY_BY_CLASS: dict[str, GraphVisibility] = {
    "ENTITY": "main_graph",
    "EVIDENCE": "evidence_only",
    "SIGNAL": "signal_badge",
    "CANDIDATE": "candidate_bin",
    "COMPLIANCE": "compliance_log",
    "NOISE": "noise_bin",
}

META_BUCKET_BY_CLASS: dict[str, str | None] = {
    "ENTITY": None,
    "EVIDENCE": "evidence",
    "SIGNAL": "signals",
    "CANDIDATE": "leads",
    "COMPLIANCE": "compliance",
    "NOISE": "noise",
}

@dataclass(frozen=True)
class ArtifactRoute:
    artifact_class: ArtifactClass
    graph_visibility: GraphVisibility
    meta_bucket: str | None
    create_entity: bool
    attach_to_parent: bool = False


def route_for_class(artifact_class: ArtifactClass) -> ArtifactRoute:
    visibility = GRAPH_VISIBILITY_BY_CLASS[artifact_class]
    bucket = META_BUCKET_BY_CLASS[artifact_class]
    return ArtifactRoute(
        artifact_class=artifact_class,
        graph_visibility=visibility,
        meta_bucket=bucket,
        create_entity=artifact_class == "ENTITY",
        attach_to_parent=artifact_class == "SIGNAL",
    )
