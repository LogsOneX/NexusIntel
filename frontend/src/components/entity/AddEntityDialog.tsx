import { useEffect, useState } from "react";

const TYPES = ["username", "email", "domain", "ip", "phone", "url", "crypto_wallet", "location", "image_asset", "note", "evidence"];

export default function AddEntityDialog({ open, initialType = "username", onClose, onAdd }: { open: boolean; initialType?: string; onClose: () => void; onAdd: (value: string, type: string, lookup: boolean) => void }) {
  const [type, setType] = useState(initialType);
  const [value, setValue] = useState("");
  useEffect(() => { if (open) { setType(initialType); setValue(""); } }, [initialType, open]);
  if (!open) return null;
  return (
    <div className="dialog-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="nx-dialog add-entity-dialog" role="dialog" aria-modal="true" aria-label="Add entity" onMouseDown={(event) => event.stopPropagation()}>
        <header><strong>Add Entity</strong><span>Create a graph seed without inserting fake intelligence.</span></header>
        <label><span>Entity type</span><select value={type} onChange={(event) => setType(event.target.value)}>{TYPES.map((item) => <option key={item} value={item}>{item.replaceAll("_", " ")}</option>)}</select></label>
        <label><span>Value</span><input autoFocus value={value} onChange={(event) => setValue(event.target.value)} placeholder="username, email, domain, IP, phone, URL" /></label>
        <footer><button type="button" onClick={onClose}>Cancel</button><button type="button" disabled={!value.trim()} onClick={() => { onAdd(value.trim(), type, false); onClose(); }}>Add only</button><button className="primary" type="button" disabled={!value.trim()} onClick={() => { onAdd(value.trim(), type, true); onClose(); }}>Add and Lookup</button></footer>
      </section>
    </div>
  );
}
