export type EntityGroup = "Identity" | "Contact" | "Infrastructure" | "Geo" | "Asset" | "Crypto" | "Analyst";

export type EntityTypeDefinition = {
  type: string;
  label: string;
  description: string;
  group: EntityGroup;
  enabled: boolean;
  mapsTo?: string;
};

export const ENTITY_TYPES: EntityTypeDefinition[] = [
  { group: "Identity", type: "username", label: "Username", description: "Public handle or account alias", enabled: true },
  { group: "Identity", type: "name", label: "Person/Alias", description: "Name, alias, or persona label", enabled: true },
  { group: "Identity", type: "profile", label: "Profile", description: "Public profile URL or profile entity", enabled: true },
  { group: "Contact", type: "email", label: "Email", description: "Mailbox or account identifier", enabled: true },
  { group: "Contact", type: "phone", label: "Phone", description: "E.164 phone number or contact point", enabled: true },
  { group: "Infrastructure", type: "domain", label: "Domain", description: "DNS and web surface", enabled: true },
  { group: "Infrastructure", type: "url", label: "URL", description: "Specific public URL", enabled: true },
  { group: "Infrastructure", type: "ip", label: "IP Address", description: "IPv4 or IPv6 network address", enabled: true },
  { group: "Infrastructure", type: "dns_record", label: "DNS Record", description: "DNS answer or resolver artifact", enabled: true },
  { group: "Geo", type: "google_maps_profile", label: "Google Maps Profile", description: "Analyst-supplied public Maps profile URL", enabled: true },
  { group: "Geo", type: "location", label: "Location", description: "Place, venue, or location entity", enabled: true },
  { group: "Geo", type: "place", label: "Place", description: "Public place or venue record", enabled: true },
  { group: "Asset", type: "image_asset", label: "Image Asset", description: "Image, avatar, logo, or screenshot", enabled: true },
  { group: "Asset", type: "favicon", label: "Favicon", description: "Website icon or favicon pivot", enabled: true },
  { group: "Asset", type: "hash", label: "Hash", description: "File, image, favicon, or content hash", enabled: true },
  { group: "Asset", type: "document", label: "Document", description: "Public document or file reference", enabled: true },
  { group: "Crypto", type: "crypto_wallet", label: "Crypto Wallet", description: "Public blockchain wallet address", enabled: true },
  { group: "Crypto", type: "crypto_transaction", label: "Transaction", description: "Public blockchain transaction", enabled: true },
  { group: "Analyst", type: "note", label: "Note", description: "Analyst note attached to the case", enabled: true },
  { group: "Analyst", type: "evidence", label: "Evidence", description: "Source URL, proof pointer, or evidence ref", enabled: true },
];

export const ENTITY_GROUPS: EntityGroup[] = ["Identity", "Contact", "Infrastructure", "Geo", "Asset", "Crypto", "Analyst"];

export function entityLabelFor(type: string): string {
  return ENTITY_TYPES.find((item) => item.type === type)?.label || type.replaceAll("_", " ");
}
