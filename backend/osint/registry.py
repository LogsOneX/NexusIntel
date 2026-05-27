from __future__ import annotations

from dataclasses import asdict

from backend.osint.adapters.domain import DomainCTAdapter, DomainDNSAdapter, DomainRDAPAdapter, IPRDAPAdapter, WebFingerprintAdapter
from backend.osint.adapters.email import EmailDomainWorkspaceAdapter, EmailSyntaxAdapter, GitHubPublicSearchAdapter, GravatarAdapter, HIBPAdapter, UsernameCandidateAdapter
from backend.osint.adapters.identity import UsernameProfilesAdapter
from backend.osint.adapters.maps import MapsProfileReviewsAdapter
from backend.osint.adapters.phone import PhoneNumberingPlanAdapter
from backend.osint.types import OSINTAdapter, TransformDefinition


def default_adapters() -> list[OSINTAdapter]:
    return [
        EmailSyntaxAdapter(),
        EmailDomainWorkspaceAdapter(),
        GravatarAdapter(),
        GitHubPublicSearchAdapter(),
        HIBPAdapter(),
        UsernameCandidateAdapter(),
        UsernameProfilesAdapter(),
        DomainDNSAdapter(),
        DomainRDAPAdapter(),
        DomainCTAdapter(),
        WebFingerprintAdapter(),
        IPRDAPAdapter(),
        PhoneNumberingPlanAdapter(),
        MapsProfileReviewsAdapter(),
    ]


def default_transforms() -> list[TransformDefinition]:
    return [
        TransformDefinition("email_to_workspace", "Email -> Workspace", "DNS MX/TXT workspace posture.", ["email"], ["domain", "mx_record", "txt_record", "workspace_signal"], "email.domain_workspace"),
        TransformDefinition("email_to_gravatar", "Email -> Gravatar", "MD5 lowercase email hash and public Gravatar avatar/profile endpoints.", ["email"], ["avatar", "avatar_hash", "public_profile"], "email.gravatar"),
        TransformDefinition("email_to_breach_connectors", "Email -> Breach Connectors", "Official HIBP API only, BYOK required.", ["email"], ["breach_record"], "email.hibp", True, ["HIBP_API_KEY"]),
        TransformDefinition("email_to_username_candidates", "Email -> Username Candidates", "Low-confidence local-part candidate generation. Results go to the candidate lead bin until promoted.", ["email"], ["username_candidate"], "email.username_candidates"),
        TransformDefinition(
            "email_to_public_profiles",
            "Email -> Public Profile Pivot (Playbook)",
            "Disabled as a direct transform: derive username candidates from the email, promote a candidate, then run Username -> Profiles.",
            ["email"],
            ["username_candidate", "public_profile"],
            "playbook.email_public_profile_pivot",
            enabled=False,
            disabled_reason="not_implemented_as_direct_transform;use_email_to_username_candidates_then_username_to_profiles",
        ),
        TransformDefinition("email_to_github_public_search", "Email -> GitHub Public Search", "Official GitHub public code search, BYOK required.", ["email"], ["public_code_hit"], "email.github_public_search", True, ["GITHUB_TOKEN"]),
        TransformDefinition("username_to_profiles", "Username -> Profiles", "Curated public profile presence checks with false-positive heuristics.", ["username"], ["public_profile", "platform", "external_link", "avatar"], "username.public_profiles"),
        TransformDefinition("profile_to_links", "Profile -> Links", "Fetch public profile/web page metadata and outgoing links.", ["public_profile", "profile", "url"], ["external_link", "web_fingerprint"], "domain.web_fingerprint"),
        TransformDefinition("profile_to_avatar", "Profile/URL -> Web Fingerprint", "Disabled until a dedicated avatar extractor exists; use Profile -> Links for public page metadata.", ["public_profile", "url"], ["avatar"], "domain.web_fingerprint", enabled=False, disabled_reason="not_implemented_avatar_extractor"),
        TransformDefinition("avatar_to_hashes", "Avatar -> Hashes", "Hash analyst-provided or public image evidence.", ["avatar", "image_asset"], ["image_hash"], "image.hashes", enabled=False, disabled_reason="adapter_not_implemented"),
        TransformDefinition("image_to_reuse_candidates", "Image -> Reuse Candidates", "Search local case asset hashes for reuse.", ["image_asset", "avatar"], ["reuse_candidate"], "image.reuse_candidates", enabled=False, disabled_reason="adapter_not_implemented"),
        TransformDefinition("domain_to_dns", "Domain -> DNS", "A/AAAA/MX/NS/TXT/CAA records.", ["domain"], ["dns_record", "ip", "mx_record", "txt_record"], "domain.dns"),
        TransformDefinition("domain_to_rdap", "Domain -> RDAP", "Public RDAP domain metadata.", ["domain"], ["rdap_record", "nameserver"], "domain.rdap"),
        TransformDefinition("domain_to_ct_subdomains", "Domain -> CT Subdomains", "crt.sh public CT subdomains.", ["domain"], ["subdomain"], "domain.ct_subdomains"),
        TransformDefinition("domain_to_favicon_hash", "Domain -> Favicon Hash", "Disabled until a dedicated favicon hash collector is implemented; use Domain -> Web Fingerprint for public page metadata.", ["domain", "url"], ["favicon_hash"], "domain.web_fingerprint", enabled=False, disabled_reason="not_implemented_favicon_hash_collector"),
        TransformDefinition("domain_to_web_fingerprint", "Domain -> Web Fingerprint", "HTTP headers, title, meta, external links.", ["domain", "url"], ["web_fingerprint", "external_link"], "domain.web_fingerprint"),
        TransformDefinition("domain_to_urlscan", "Domain -> URLScan", "Official URLScan connector, BYOK required.", ["domain", "url"], ["urlscan_result"], "connector.urlscan", True, ["URLSCAN_API_KEY"], enabled=False, disabled_reason="adapter_not_implemented"),
        TransformDefinition("ip_to_rdap_asn", "IP -> RDAP/ASN", "Public RDAP allocation metadata.", ["ip"], ["rdap_record", "asn"], "ip.rdap_asn"),
        TransformDefinition("ip_to_reverse_dns", "IP -> Reverse DNS", "Disabled until a dedicated passive reverse-DNS collector is implemented; use IP -> RDAP/ASN for allocation metadata.", ["ip"], ["domain"], "ip.rdap_asn", enabled=False, disabled_reason="not_implemented_reverse_dns_collector"),
        TransformDefinition("phone_to_numbering_plan", "Phone -> Numbering Plan", "E.164 and public numbering-plan metadata.", ["phone"], ["phone_posture"], "phone.numbering_plan"),
        TransformDefinition("phone_to_public_deeplinks", "Phone -> Public Deeplinks", "Disabled: generic messenger deeplinks are noisy and do not prove account presence.", ["phone"], ["public_deeplink"], "phone.numbering_plan", enabled=False, disabled_reason="not_implemented_noise_risk"),
        TransformDefinition("maps_profile_to_reviews", "Maps Profile -> Reviews", "Analyst-supplied public Google Maps profile URL reviews.", ["google_maps_profile", "url"], ["google_maps_review", "google_maps_place"], "maps.profile_reviews"),
        TransformDefinition("maps_profile_to_photos", "Maps Profile -> Photos", "Disabled until Maps photo extraction is implemented; use Maps Profile -> Reviews for visible public profile metadata.", ["google_maps_profile", "url"], ["google_maps_photo"], "maps.profile_reviews", enabled=False, disabled_reason="not_implemented_photo_extractor"),
        TransformDefinition("maps_place_to_place_details", "Maps Place -> Place Details", "Google Places API enrichment, BYOK only.", ["google_maps_place", "location"], ["place_detail"], "connector.google_places", True, ["GOOGLE_MAPS_API_KEY"], enabled=False, disabled_reason="adapter_not_implemented"),
        TransformDefinition("spiderfoot_csv_import", "SpiderFoot CSV Import", "Preview/import SpiderFoot CSV preserving source/confidence.", ["file"], ["ioc", "domain", "ip", "email"], "importer.spiderfoot_csv", enabled=False, disabled_reason="use_import_preview_endpoint"),
        TransformDefinition("maltego_csv_import", "Maltego CSV Import", "Preview/import Maltego CSV with mapping.", ["file"], ["entity"], "importer.maltego_csv", enabled=False, disabled_reason="use_import_preview_endpoint"),
    ]


class AdapterRegistry:
    def __init__(self) -> None:
        self.adapters = {adapter.id: adapter for adapter in default_adapters()}
        self.transforms = {transform.id: transform for transform in default_transforms()}

    def get_adapter(self, adapter_id: str) -> OSINTAdapter | None:
        return self.adapters.get(adapter_id)

    def get_transform(self, transform_id: str) -> TransformDefinition | None:
        return self.transforms.get(transform_id)

    def list_adapters(self) -> list[dict]:
        return [
            {
                "id": adapter.id,
                "name": adapter.name,
                "description": adapter.description,
                "input_types": adapter.input_types,
                "output_types": adapter.output_types,
                "requires_api_key": adapter.requires_api_key,
                "passive": adapter.passive,
                "legal_note": adapter.legal_note,
                "rate_limit": asdict(adapter.rate_limit),
            }
            for adapter in self.adapters.values()
        ]

    def list_transforms(self, configured_keys: set[str] | None = None) -> list[dict]:
        items: list[dict] = []
        for transform in self.transforms.values():
            data = transform.to_dict(configured_keys)
            if transform.adapter_id not in self.adapters:
                data["enabled"] = False
                reason = data.get("disabled_reason")
                data["disabled_reason"] = f"{reason};adapter_not_implemented" if reason else "adapter_not_implemented"
            items.append(data)
        return items

    def validate_registry(self, configured_keys: set[str] | None = None) -> dict:
        configured = configured_keys or set()
        errors: list[dict] = []
        warnings: list[dict] = []
        transform_diagnostics: list[dict] = []
        adapter_diagnostics = [
            {
                "adapter_id": adapter.id,
                "implemented": adapter.id != "base",
                "input_types": adapter.input_types,
                "output_types": adapter.output_types,
                "requires_api_key": adapter.requires_api_key,
                "passive": adapter.passive,
            }
            for adapter in self.adapters.values()
        ]
        for transform in self.transforms.values():
            adapter = self.adapters.get(transform.adapter_id)
            missing_keys = [key for key in transform.required_keys if key not in configured]
            input_ok = bool(adapter and ("*" in transform.input_types or set(adapter.input_types).intersection(transform.input_types)))
            output_ok = bool(transform.output_types)
            implemented = adapter is not None
            enabled = transform.enabled and implemented and not missing_keys
            reasons: list[str] = []
            if not implemented:
                reasons.append("adapter_not_implemented")
            if not transform.enabled:
                reasons.append(transform.disabled_reason or "disabled_by_registry")
            if missing_keys:
                reasons.append("missing_api_key:" + ",".join(missing_keys))
            if implemented and not input_ok:
                reasons.append("input_type_mismatch")
                warnings.append({"transform_id": transform.id, "adapter_id": transform.adapter_id, "warning": "input_type_mismatch"})
            if not output_ok:
                reasons.append("missing_output_types")
                errors.append({"transform_id": transform.id, "adapter_id": transform.adapter_id, "error": "missing_output_types"})
            if implemented and transform.enabled and not set(transform.output_types).intersection(adapter.output_types):
                warnings.append({"transform_id": transform.id, "adapter_id": transform.adapter_id, "warning": "output_types_do_not_overlap_adapter_outputs"})
            if not implemented and transform.enabled:
                errors.append({"transform_id": transform.id, "adapter_id": transform.adapter_id, "error": "enabled_transform_missing_adapter"})
            transform_diagnostics.append({
                "transform_id": transform.id,
                "label": transform.label,
                "adapter_id": transform.adapter_id,
                "implemented": implemented,
                "enabled": enabled,
                "input_types": transform.input_types,
                "adapter_input_types": adapter.input_types if adapter else [],
                "input_compatible": input_ok,
                "output_types": transform.output_types,
                "adapter_output_types": adapter.output_types if adapter else [],
                "required_keys": transform.required_keys,
                "missing_keys": missing_keys,
                "status": "enabled" if enabled else "disabled",
                "reasons": reasons,
            })
        disabled = [item for item in transform_diagnostics if item["status"] != "enabled"]
        missing_adapters = [item for item in transform_diagnostics if not item["implemented"]]
        missing_api_keys = sorted({key for item in transform_diagnostics for key in item.get("missing_keys", [])})
        count_by_entity_type: dict[str, int] = {}
        count_by_connector: dict[str, int] = {}
        source_reliability_by_transform: dict[str, str] = {}
        for transform in self.transforms.values():
            for entity_type in transform.input_types:
                count_by_entity_type[entity_type] = count_by_entity_type.get(entity_type, 0) + 1
            connector = transform.adapter_id.split(".", 1)[0]
            count_by_connector[connector] = count_by_connector.get(connector, 0) + 1
            if transform.requires_api_key:
                source_reliability_by_transform[transform.id] = "official_api_byok"
            elif transform.adapter_id.startswith(("domain.", "ip.", "email.domain_workspace")):
                source_reliability_by_transform[transform.id] = "primary_public_source"
            elif "import" in transform.adapter_id:
                source_reliability_by_transform[transform.id] = "analyst_provided"
            else:
                source_reliability_by_transform[transform.id] = "public_web_or_derived"
        recommended_connector_setup = []
        for key in missing_api_keys:
            unlocked = [item["transform_id"] for item in transform_diagnostics if key in item.get("missing_keys", [])]
            recommended_connector_setup.append({"key": key, "unlocks": unlocked, "reason": "Optional BYOK connector is unavailable until configured."})
        return {
            "errors": errors,
            "critical_errors": errors,
            "warnings": warnings,
            "disabled_transforms": disabled,
            "missing_adapters": missing_adapters,
            "missing_api_keys": missing_api_keys,
            "transform_count_by_entity_type": count_by_entity_type,
            "transform_count_by_connector": count_by_connector,
            "source_reliability_by_transform": source_reliability_by_transform,
            "recommended_connector_setup": recommended_connector_setup,
            "transforms": transform_diagnostics,
            "adapters": adapter_diagnostics,
        }


registry = AdapterRegistry()
