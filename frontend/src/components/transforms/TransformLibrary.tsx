import { useMemo, useState } from "react";
import { GitBranch, Search } from "lucide-react";
import type { ApiNode, TransformDefinition } from "../../lib/types";
import EmptyState from "../common/EmptyState";
import TransformCard from "./TransformCard";

export const FALLBACK_TRANSFORMS: TransformDefinition[] = [
  { id: "email_to_workspace", label: "Email -> Workspace", description: "Resolve public mail and workspace posture from DNS and official connectors.", input_types: ["email"], output_types: ["domain", "workspace"], adapter_id: "email_workspace", requires_api_key: false, enabled: true, passive: true, confidence_profile: "direct DNS" },
  { id: "email_to_gravatar", label: "Email -> Gravatar", description: "Check public Gravatar hash/avatar evidence.", input_types: ["email"], output_types: ["avatar", "profile"], adapter_id: "gravatar", requires_api_key: false, enabled: true, passive: true },
  { id: "email_to_public_profiles", label: "Email -> Public Profiles", description: "Search configured official/public connectors for exact public email appearances.", input_types: ["email"], output_types: ["profile"], adapter_id: "email_profiles", requires_api_key: true, required_keys: ["github"], enabled: false, disabled_reason: "Connector key required" },
  { id: "username_to_profiles", label: "Username -> Profiles", description: "Resolve public profile pages with false-positive scoring.", input_types: ["username", "name"], output_types: ["profile"], adapter_id: "identity", requires_api_key: false, enabled: true, passive: true },
  { id: "profile_to_links", label: "Profile -> Links", description: "Extract public external links from profile artifacts.", input_types: ["profile"], output_types: ["url", "domain"], adapter_id: "profile_links", requires_api_key: false, enabled: true, passive: true },
  { id: "domain_to_dns", label: "Domain -> DNS", description: "Collect DNS A/AAAA/MX/NS/TXT/CAA records.", input_types: ["domain"], output_types: ["dns_record", "ip"], adapter_id: "dns", requires_api_key: false, enabled: true, passive: true },
  { id: "domain_to_rdap", label: "Domain -> RDAP", description: "Collect public registration and allocation data.", input_types: ["domain", "ip"], output_types: ["organization", "asn"], adapter_id: "rdap", requires_api_key: false, enabled: true, passive: true },
  { id: "domain_to_ct_subdomains", label: "Domain -> CT Subdomains", description: "Enumerate passive certificate transparency names.", input_types: ["domain"], output_types: ["domain"], adapter_id: "ct", requires_api_key: false, enabled: true, passive: true },
  { id: "domain_to_favicon_hash", label: "Domain -> Favicon Hash", description: "Fetch favicon and compute reuse pivots.", input_types: ["domain", "url"], output_types: ["image_asset", "hash"], adapter_id: "favicon", requires_api_key: false, enabled: true, passive: true },
  { id: "ip_to_rdap_asn", label: "IP -> RDAP ASN", description: "Resolve public network allocation and ASN owner.", input_types: ["ip"], output_types: ["asn", "organization"], adapter_id: "ip_rdap", requires_api_key: false, enabled: true, passive: true },
  { id: "phone_to_numbering_plan", label: "Phone -> Numbering Plan", description: "Validate E.164 and public numbering metadata.", input_types: ["phone"], output_types: ["phone_metadata"], adapter_id: "phone_plan", requires_api_key: false, enabled: true, passive: true },
  { id: "maps_profile_to_reviews", label: "Maps Profile -> Reviews", description: "Parse analyst-supplied public Maps profile evidence.", input_types: ["google_maps_profile"], output_types: ["google_maps_review", "google_maps_place"], adapter_id: "maps_public", requires_api_key: false, enabled: true, passive: true },
  { id: "image_to_hashes", label: "Image -> Hashes", description: "Extract cryptographic and perceptual hashes from image assets.", input_types: ["image_asset", "avatar"], output_types: ["hash"], adapter_id: "image", requires_api_key: false, enabled: true, passive: true },
  { id: "spiderfoot_csv_import", label: "SpiderFoot CSV Import", description: "Import public-source SpiderFoot output with mapping preview.", input_types: ["file"], output_types: ["entity"], adapter_id: "importer", requires_api_key: false, enabled: true, passive: true },
];

export default function TransformLibrary({ transforms, selectedNode, onRun, loadingId, title = "Transform Library" }: { transforms?: TransformDefinition[]; selectedNode?: ApiNode | null; onRun?: (id: string) => void; loadingId?: string | null; title?: string }) {
  const [query, setQuery] = useState("");
  const source = transforms?.length ? transforms : FALLBACK_TRANSFORMS.map((item) => ({ ...item, enabled: false, source_category: item.source_category || "fallback", confidence_profile: item.confidence_profile || "fallback registry", disabled_reason: item.disabled_reason || "Registry unavailable — fallback transform catalog shown" }));
  const rows = useMemo(() => {
    const term = query.trim().toLowerCase();
    return source.filter((item) => (!term || `${item.id} ${item.label} ${item.description} ${item.output_types.join(" ")}`.toLowerCase().includes(term)));
  }, [query, source]);
  return (
    <section className="transform-library">
      <header><div><GitBranch size={15} /><strong>{title}</strong></div><label><Search size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter transforms" /></label></header>
      {!rows.length ? <EmptyState title="No transform definitions" message="The registry endpoint returned no compatible transforms." icon={GitBranch} /> : <div className="transform-grid">{rows.map((item) => <TransformCard key={item.id} transform={item} selectedNode={selectedNode} onRun={onRun} loading={loadingId === item.id} />)}</div>}
    </section>
  );
}

