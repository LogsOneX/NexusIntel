# Transform Registry Audit

This audit records the production transform registry contract after the enterprise transform-system cleanup. Backend registry definitions remain the source of truth; frontend fallback catalogs are disabled when the registry is unavailable.

- Critical errors: 0
- Warnings: 0

| Transform ID | Adapter ID | Implemented | Status | Input Compatibility | Outputs | Evidence Behavior / Limitations |
| --- | --- | --- | --- | --- | --- | --- |
| `email_to_workspace` | `email.domain_workspace` | yes | enabled | email -> email: yes | domain, mx_record, txt_record, workspace_signal | ok |
| `email_to_gravatar` | `email.gravatar` | yes | enabled | email -> email: yes | avatar, avatar_hash, public_profile | ok |
| `email_to_breach_connectors` | `email.hibp` | yes | disabled | email -> email: yes | breach_record | missing_api_key:HIBP_API_KEY |
| `email_to_username_candidates` | `email.username_candidates` | yes | enabled | email -> email: yes | username_candidate | ok |
| `email_to_public_profiles` | `playbook.email_public_profile_pivot` | no | disabled | email -> none: no | username_candidate, public_profile | adapter_not_implemented, not_implemented_as_direct_transform;use_email_to_username_candidates_then_username_to_profiles |
| `email_to_github_public_search` | `email.github_public_search` | yes | disabled | email -> email: yes | public_code_hit | missing_api_key:GITHUB_TOKEN |
| `username_to_profiles` | `username.public_profiles` | yes | enabled | username -> username: yes | public_profile, platform, external_link, avatar | ok |
| `profile_to_links` | `domain.web_fingerprint` | yes | enabled | public_profile/profile/url -> domain/url: yes | external_link, web_fingerprint | ok |
| `profile_to_avatar` | `domain.web_fingerprint` | yes | disabled | public_profile/url -> domain/url: yes | avatar | not_implemented_avatar_extractor |
| `avatar_to_hashes` | `image.hashes` | no | disabled | avatar/image_asset -> none: no | image_hash | adapter_not_implemented, adapter_not_implemented |
| `image_to_reuse_candidates` | `image.reuse_candidates` | no | disabled | image_asset/avatar -> none: no | reuse_candidate | adapter_not_implemented, adapter_not_implemented |
| `domain_to_dns` | `domain.dns` | yes | enabled | domain -> domain: yes | dns_record, ip, mx_record, txt_record | ok |
| `domain_to_rdap` | `domain.rdap` | yes | enabled | domain -> domain: yes | rdap_record, nameserver | ok |
| `domain_to_ct_subdomains` | `domain.ct_subdomains` | yes | enabled | domain -> domain: yes | subdomain | ok |
| `domain_to_favicon_hash` | `domain.web_fingerprint` | yes | disabled | domain/url -> domain/url: yes | favicon_hash | not_implemented_favicon_hash_collector |
| `domain_to_web_fingerprint` | `domain.web_fingerprint` | yes | enabled | domain/url -> domain/url: yes | web_fingerprint, external_link | ok |
| `domain_to_urlscan` | `connector.urlscan` | no | disabled | domain/url -> none: no | urlscan_result | adapter_not_implemented, adapter_not_implemented, missing_api_key:URLSCAN_API_KEY |
| `ip_to_rdap_asn` | `ip.rdap_asn` | yes | enabled | ip -> ip: yes | rdap_record, asn | ok |
| `ip_to_reverse_dns` | `ip.rdap_asn` | yes | disabled | ip -> ip: yes | domain | not_implemented_reverse_dns_collector |
| `phone_to_numbering_plan` | `phone.numbering_plan` | yes | enabled | phone -> phone: yes | phone_posture | ok |
| `phone_to_public_deeplinks` | `phone.numbering_plan` | yes | disabled | phone -> phone: yes | public_deeplink | not_implemented_noise_risk |
| `maps_profile_to_reviews` | `maps.profile_reviews` | yes | enabled | google_maps_profile/url -> google_maps_profile/url: yes | google_maps_review, google_maps_place | ok |
| `maps_profile_to_photos` | `maps.profile_reviews` | yes | disabled | google_maps_profile/url -> google_maps_profile/url: yes | google_maps_photo | not_implemented_photo_extractor |
| `maps_place_to_place_details` | `connector.google_places` | no | disabled | google_maps_place/location -> none: no | place_detail | adapter_not_implemented, adapter_not_implemented, missing_api_key:GOOGLE_MAPS_API_KEY |
| `spiderfoot_csv_import` | `importer.spiderfoot_csv` | no | disabled | file -> none: no | ioc, domain, ip, email | adapter_not_implemented, use_import_preview_endpoint |
| `maltego_csv_import` | `importer.maltego_csv` | no | disabled | file -> none: no | entity | adapter_not_implemented, use_import_preview_endpoint |

## Notes

- `email_to_public_profiles` is intentionally disabled as a direct transform. The honest workflow is `email_to_username_candidates`, analyst promotion, then `username_to_profiles`.
- Candidate username artifacts are routed to the lead bin by default through `username_candidate` classification and `graph_visibility=candidate_bin`.
- BYOK transforms are disabled until keys are present; the UI exposes diagnostics rather than implying success.
- Favicon hash, reverse DNS, generic phone deeplinks, Maps photos, avatar hashing, and image reuse transforms remain disabled until dedicated adapters exist.
