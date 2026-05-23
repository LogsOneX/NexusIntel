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
        TransformDefinition("email_to_username_candidates", "Email -> Username Candidates", "Low-confidence local-part candidate generation.", ["email"], ["username"], "email.username_candidates"),
        TransformDefinition("email_to_public_profiles", "Email -> Public Profiles", "Generate username candidates then run public profile checks manually/corroborated.", ["email"], ["username"], "email.username_candidates"),
        TransformDefinition("email_to_github_public_search", "Email -> GitHub Public Search", "Official GitHub public code search, BYOK required.", ["email"], ["public_code_hit"], "email.github_public_search", True, ["GITHUB_TOKEN"]),
        TransformDefinition("username_to_profiles", "Username -> Profiles", "Curated public profile presence checks with false-positive heuristics.", ["username"], ["public_profile", "platform", "external_link", "avatar"], "username.public_profiles"),
        TransformDefinition("profile_to_links", "Profile -> Links", "Fetch public profile/web page metadata and outgoing links.", ["public_profile", "profile", "url"], ["external_link", "web_fingerprint"], "domain.web_fingerprint"),
        TransformDefinition("profile_to_avatar", "Profile -> Avatar", "Extract public avatar metadata where visible in public HTML.", ["public_profile", "url"], ["avatar"], "domain.web_fingerprint"),
        TransformDefinition("avatar_to_hashes", "Avatar -> Hashes", "Hash analyst-provided or public image evidence.", ["avatar", "image_asset"], ["image_hash"], "image.hashes"),
        TransformDefinition("image_to_reuse_candidates", "Image -> Reuse Candidates", "Search local case asset hashes for reuse.", ["image_asset", "avatar"], ["reuse_candidate"], "image.reuse_candidates"),
        TransformDefinition("domain_to_dns", "Domain -> DNS", "A/AAAA/MX/NS/TXT/CAA records.", ["domain"], ["dns_record", "ip", "mx_record", "txt_record"], "domain.dns"),
        TransformDefinition("domain_to_rdap", "Domain -> RDAP", "Public RDAP domain metadata.", ["domain"], ["rdap_record", "nameserver"], "domain.rdap"),
        TransformDefinition("domain_to_ct_subdomains", "Domain -> CT Subdomains", "crt.sh public CT subdomains.", ["domain"], ["subdomain"], "domain.ct_subdomains"),
        TransformDefinition("domain_to_favicon_hash", "Domain -> Favicon Hash", "Fetch favicon and mmh3/hash metadata when dependencies are present.", ["domain", "url"], ["favicon_hash"], "domain.web_fingerprint"),
        TransformDefinition("domain_to_web_fingerprint", "Domain -> Web Fingerprint", "HTTP headers, title, meta, external links.", ["domain", "url"], ["web_fingerprint", "external_link"], "domain.web_fingerprint"),
        TransformDefinition("domain_to_urlscan", "Domain -> URLScan", "Official URLScan connector, BYOK required.", ["domain", "url"], ["urlscan_result"], "connector.urlscan", True, ["URLSCAN_API_KEY"]),
        TransformDefinition("ip_to_rdap_asn", "IP -> RDAP/ASN", "Public RDAP allocation metadata.", ["ip"], ["rdap_record", "asn"], "ip.rdap_asn"),
        TransformDefinition("ip_to_reverse_dns", "IP -> Reverse DNS", "Public reverse DNS lookup.", ["ip"], ["domain"], "ip.rdap_asn"),
        TransformDefinition("phone_to_numbering_plan", "Phone -> Numbering Plan", "E.164 and public numbering-plan metadata.", ["phone"], ["phone_posture"], "phone.numbering_plan"),
        TransformDefinition("phone_to_public_deeplinks", "Phone -> Public Deeplinks", "Only public deeplink metadata; no registration claim.", ["phone"], ["public_deeplink"], "phone.numbering_plan"),
        TransformDefinition("maps_profile_to_reviews", "Maps Profile -> Reviews", "Analyst-supplied public Google Maps profile URL reviews.", ["google_maps_profile", "url"], ["google_maps_review", "google_maps_place"], "maps.profile_reviews"),
        TransformDefinition("maps_profile_to_photos", "Maps Profile -> Photos", "Visible public Maps image URLs in supplied profile HTML.", ["google_maps_profile", "url"], ["google_maps_photo"], "maps.profile_reviews"),
        TransformDefinition("maps_place_to_place_details", "Maps Place -> Place Details", "Google Places API enrichment, BYOK only.", ["google_maps_place", "location"], ["place_detail"], "connector.google_places", True, ["GOOGLE_MAPS_API_KEY"]),
        TransformDefinition("spiderfoot_csv_import", "SpiderFoot CSV Import", "Preview/import SpiderFoot CSV preserving source/confidence.", ["file"], ["ioc", "domain", "ip", "email"], "importer.spiderfoot_csv"),
        TransformDefinition("maltego_csv_import", "Maltego CSV Import", "Preview/import Maltego CSV with mapping.", ["file"], ["entity"], "importer.maltego_csv"),
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


registry = AdapterRegistry()
