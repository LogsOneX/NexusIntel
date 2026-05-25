import { useState } from "react";
import { AtSign, Bitcoin, FileImage, Fingerprint, Globe, GripVertical, Hash, HelpCircle, Link, MapPin, Network, NotebookPen, Phone, Search, Sparkles, UserRound, X } from "lucide-react";
import EntityTypeCard from "./EntityTypeCard";

const GROUPS = [
  { name: "Identity", items: [[UserRound, "Username", "Public handle or alias"], [Fingerprint, "Person/Alias", "Name, handle, or persona"]] },
  { name: "Contact", items: [[AtSign, "Email", "Mailbox or account identifier"], [Phone, "Phone", "E.164 phone number"]] },
  { name: "Infrastructure", items: [[Globe, "Domain", "DNS and web surface"], [Link, "URL", "Specific public URL"], [Network, "IP Address", "Network address"]] },
  { name: "Geo", items: [[MapPin, "Google Maps Profile", "Public maps profile URL"], [MapPin, "Location/Place", "Place or location entity"]] },
  { name: "Asset", items: [[FileImage, "Image Asset", "Image, avatar, or screenshot"], [Hash, "Favicon/Hash", "Asset hash pivot"]] },
  { name: "Crypto", items: [[Bitcoin, "Crypto Wallet", "Public wallet address"], [Link, "Transaction", "Public chain transaction"]] },
  { name: "Analyst", items: [[NotebookPen, "Note", "Analyst note"], [Hash, "Evidence", "Source or raw proof pointer"]] },
] as const;

function seedFor(label: string): string {
  return label.toLowerCase().replace(" address", "").replace("person/alias", "name").replace("google maps profile", "url").replace("location/place", "location").replace("favicon/hash", "hash").replace("crypto wallet", "crypto_wallet");
}

export default function EntityPaletteDrawer({ open, onClose, onPick }: { open: boolean; onClose: () => void; onPick: (kind: string) => void }) {
  const [query, setQuery] = useState("");
  const cleanQuery = query.trim().toLowerCase();
  const filteredGroups = GROUPS.map((group) => ({
    ...group,
    items: group.items.filter(([, label, description]) => !cleanQuery || label.toLowerCase().includes(cleanQuery) || description.toLowerCase().includes(cleanQuery) || group.name.toLowerCase().includes(cleanQuery)),
  })).filter((group) => group.items.length > 0);
  return (
    <aside className={open ? "entity-palette-drawer open reference-palette" : "entity-palette-drawer reference-palette"} aria-label="Entity palette" aria-hidden={!open}>
      <header><div><strong>Entity Palette</strong><span>Structured seeds and pivots</span></div><button type="button" onClick={onClose} aria-label="Close entity palette"><X size={15} /></button></header>
      <label className="ref-palette-search"><Search size={12} /><input aria-label="Search entity types" placeholder="Filter entity types..." value={query} onChange={(event) => setQuery(event.target.value)} /></label>
      <div className="entity-palette-groups">
        {filteredGroups.map((group) => <section key={group.name}><h3><span>{group.name}</span><code>{group.items.length} types</code></h3>{group.items.map(([Icon, label, description]) => <div className="ref-entity-type-row" key={label}><GripVertical size={12} /><EntityTypeCard icon={Icon} label={label} description={description} onClick={() => onPick(seedFor(label))} /><span>+ ADD NODE</span></div>)}</section>)}
        {!filteredGroups.length && <div className="ref-palette-empty"><HelpCircle size={28} /><strong>No entity types found</strong><span>Try a different metadata label.</span></div>}
      </div>
      <footer className="ref-palette-footer"><Sparkles size={11} /><span>Standard IOC profiles loaded internally</span></footer>
    </aside>
  );
}
