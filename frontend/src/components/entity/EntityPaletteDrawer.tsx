import { AtSign, Bitcoin, FileImage, Fingerprint, Globe, Hash, Link, MapPin, Network, NotebookPen, Phone, UserRound, X } from "lucide-react";
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
  return (
    <aside className={open ? "entity-palette-drawer open" : "entity-palette-drawer"} aria-label="Entity palette" aria-hidden={!open}>
      <header><div><strong>Entity Palette</strong><span>Structured seeds and pivots</span></div><button type="button" onClick={onClose} aria-label="Close entity palette"><X size={15} /></button></header>
      <input aria-label="Search entity types" placeholder="Search entity type" />
      <div className="entity-palette-groups">
        {GROUPS.map((group) => <section key={group.name}><h3>{group.name}</h3>{group.items.map(([Icon, label, description]) => <EntityTypeCard key={label} icon={Icon} label={label} description={description} onClick={() => onPick(seedFor(label))} />)}</section>)}
      </div>
    </aside>
  );
}
