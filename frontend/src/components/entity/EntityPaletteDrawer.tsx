import { useState } from "react";
import type { LucideIcon } from "lucide-react";
import { AtSign, Bitcoin, FileImage, FileText, Fingerprint, Globe, GripVertical, Hash, HelpCircle, IdCard, Link, MapPin, MapPinned, Network, NotebookPen, Phone, ReceiptText, Search, Server, Sparkles, UserRound, X } from "lucide-react";
import EntityTypeCard from "./EntityTypeCard";
import { ENTITY_GROUPS, ENTITY_TYPES, type EntityGroup } from "../../lib/entityTypes";

const TYPE_ICONS: Record<string, LucideIcon> = {
  username: Fingerprint,
  name: UserRound,
  profile: IdCard,
  email: AtSign,
  phone: Phone,
  domain: Globe,
  url: Link,
  ip: Network,
  dns_record: Server,
  google_maps_profile: MapPin,
  location: MapPin,
  place: MapPinned,
  image_asset: FileImage,
  favicon: FileImage,
  hash: Hash,
  document: FileText,
  crypto_wallet: Bitcoin,
  crypto_transaction: ReceiptText,
  note: NotebookPen,
  evidence: FileText,
};

const GROUP_ACCENT: Record<EntityGroup, string> = {
  Identity: "identity",
  Contact: "contact",
  Infrastructure: "infrastructure",
  Geo: "geo",
  Asset: "asset",
  Crypto: "crypto",
  Analyst: "analyst",
};

export default function EntityPaletteDrawer({ open, onClose, onPick }: { open: boolean; onClose: () => void; onPick: (kind: string) => void }) {
  const [query, setQuery] = useState("");
  const cleanQuery = query.trim().toLowerCase();
  const filteredGroups = ENTITY_GROUPS.map((group) => ({
    name: group,
    items: ENTITY_TYPES.filter((item) => item.group === group).filter((item) => !cleanQuery || item.label.toLowerCase().includes(cleanQuery) || item.description.toLowerCase().includes(cleanQuery) || item.type.toLowerCase().includes(cleanQuery) || group.toLowerCase().includes(cleanQuery)),
  })).filter((group) => group.items.length > 0);
  return (
    <aside className={open ? "nexus-drawer-left entity-palette-drawer open reference-palette" : "nexus-drawer-left entity-palette-drawer reference-palette"} aria-label="Entity palette" aria-hidden={!open}>
      <header><div><strong>Entity Palette</strong><span>Structured seeds and pivots</span></div><button type="button" onClick={onClose} aria-label="Close entity palette"><X size={15} /></button></header>
      <label className="ref-palette-search"><Search size={12} /><input aria-label="Search entity types" placeholder="Filter entity types..." value={query} onChange={(event) => setQuery(event.target.value)} /></label>
      <div className="entity-palette-groups">
        {filteredGroups.map((group) => (
          <section key={group.name}>
            <h3><span>{group.name}</span><code>{group.items.length} types</code></h3>
            {group.items.map((item) => {
              const Icon = TYPE_ICONS[item.type] || HelpCircle;
              return (
                <div className={`ref-entity-type-row ${GROUP_ACCENT[item.group]}${item.enabled ? "" : " disabled"}`} key={item.type}>
                  <GripVertical size={12} />
                  <EntityTypeCard icon={Icon} label={item.label} description={item.description} onClick={() => item.enabled && onPick(item.mapsTo || item.type)} />
                  <span>{item.enabled ? "+ ADD NODE" : "UNSUPPORTED"}</span>
                </div>
              );
            })}
          </section>
        ))}
        {!filteredGroups.length && <div className="ref-palette-empty"><HelpCircle size={28} /><strong>No entity types found</strong><span>Try a different metadata label.</span></div>}
      </div>
      <footer className="ref-palette-footer"><Sparkles size={11} /><span>Standard IOC profiles loaded internally</span></footer>
    </aside>
  );
}
