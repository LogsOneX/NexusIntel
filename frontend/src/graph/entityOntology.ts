export const ENTITY_FAMILIES: Record<string, string[]> = {
  identity: ["username", "person_alias", "name", "profile", "account"],
  contact: ["email", "phone", "masked_email", "masked_phone", "censored_email", "censored_phone"],
  infrastructure: ["domain", "url", "ip", "dns_record", "certificate", "service", "technology"],
  geo: ["location", "place", "google_maps_profile", "google_maps_review", "google_maps_photo"],
  asset: ["image_asset", "avatar", "favicon", "document", "file_hash"],
  crypto: ["crypto_wallet", "crypto_transaction", "transaction"],
  threat: ["suspicious_domain", "risk", "breach_record", "indicator"],
  system: ["target", "investigation_root", "note"],
};

export function familyForEntity(type: string): string {
  const normalized = type.toLowerCase();
  return Object.entries(ENTITY_FAMILIES).find(([, types]) => types.includes(normalized))?.[0] || "identity";
}

export const NON_GRAPH_ARTIFACT_TYPES = new Set(["guardrail", "skipped_check", "legal_note", "policy", "compliance", "blocked_transform", "prohibited_probe_notice", "profile_candidate", "candidate_profile", "candidate_url_only", "generic_login_page", "auth_wall_only", "soft_404", "parked_domain"]);
