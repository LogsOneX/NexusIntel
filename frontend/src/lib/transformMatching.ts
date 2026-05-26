import type { ApiNode, TransformDefinition } from "./types";

const TYPE_ALIASES: Record<string, string[]> = {
  ip: ["ip", "ip_address", "ipv4", "ipv6", "host_ip"],
  url: ["url", "uri", "website", "web", "link"],
  google_profile: ["google_profile", "google_maps_profile", "google_maps_place", "maps_profile"],
  wallet: ["wallet", "crypto_wallet", "cryptocurrency_wallet", "address"],
  profile: ["profile", "public_profile", "social_profile", "person_alias", "alias", "name"],
  username: ["username", "username_candidate", "email_local_part", "handle", "screen_name", "user"],
  domain: ["domain", "hostname", "fqdn"],
  email: ["email", "email_address"],
  phone: ["phone", "phone_number", "e164"],
  image_asset: ["image_asset", "image", "avatar", "file_image"],
};

function cleanType(type: string): string {
  return String(type || "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9*]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

export function normalizeEntityType(type: string): string {
  const clean = cleanType(type);
  if (!clean) return "";
  if (clean === "*") return "*";
  for (const [canonical, aliases] of Object.entries(TYPE_ALIASES)) {
    if (canonical === clean || aliases.includes(clean)) return canonical;
  }
  return clean;
}

function typeAlternates(type: string): Set<string> {
  const canonical = normalizeEntityType(type);
  const alternates = new Set<string>([canonical]);
  const aliases = TYPE_ALIASES[canonical] || [];
  aliases.forEach((alias) => alternates.add(normalizeEntityType(alias)));
  Object.entries(TYPE_ALIASES).forEach(([key, aliasesForKey]) => {
    if (aliasesForKey.map(normalizeEntityType).includes(canonical)) {
      alternates.add(normalizeEntityType(key));
      aliasesForKey.forEach((alias) => alternates.add(normalizeEntityType(alias)));
    }
  });
  alternates.delete("");
  return alternates;
}

export function transformMatchesEntity(transform: TransformDefinition, entityType: string): boolean {
  const inputs = transform.input_types || [];
  if (!inputs.length) return false;
  if (inputs.some((item) => normalizeEntityType(item) === "*")) return true;
  const entityTypes = typeAlternates(entityType);
  return inputs.some((input) => entityTypes.has(normalizeEntityType(input)));
}

export function compatibleTransformsForNode(transforms: TransformDefinition[], node: Pick<ApiNode, "type"> | null): TransformDefinition[] {
  if (!node?.type) return [];
  return transforms.filter((transform) => transformMatchesEntity(transform, node.type));
}
