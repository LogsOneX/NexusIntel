import { useEffect, useMemo, useRef, useState } from "react";
import { Command, Search } from "lucide-react";
import type { CommandItem } from "../../lib/types";

export default function CommandPalette({ open, commands, onClose }: { open: boolean; commands: CommandItem[]; onClose: () => void }) {
  const [query, setQuery] = useState("");
  const [index, setIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const filtered = useMemo(() => {
    const term = query.trim().toLowerCase();
    return commands.filter((item) => !term || `${item.label} ${item.description || ""} ${item.group || ""}`.toLowerCase().includes(term));
  }, [commands, query]);

  useEffect(() => {
    if (!open) return;
    setQuery("");
    setIndex(0);
    window.setTimeout(() => inputRef.current?.focus(), 20);
  }, [open]);

  useEffect(() => {
    if (!open) return undefined;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key === "ArrowDown") { event.preventDefault(); setIndex((current) => Math.min(current + 1, Math.max(filtered.length - 1, 0))); }
      if (event.key === "ArrowUp") { event.preventDefault(); setIndex((current) => Math.max(current - 1, 0)); }
      if (event.key === "Enter" && filtered[index] && !filtered[index].disabled) {
        event.preventDefault();
        filtered[index].action();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [filtered, index, onClose, open]);

  if (!open) return null;
  return (
    <div className="command-palette-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="command-palette" role="dialog" aria-modal="true" aria-label="Command palette" onMouseDown={(event) => event.stopPropagation()}>
        <header><Command size={17} /><strong>Command Palette</strong><span>Ctrl K</span></header>
        <label className="palette-search"><Search size={15} /><input ref={inputRef} value={query} onChange={(event) => { setQuery(event.target.value); setIndex(0); }} placeholder="Search command, page, transform, or action" /></label>
        <div className="palette-results">
          {filtered.map((item, itemIndex) => (
            <button className={itemIndex === index ? "active" : ""} key={item.id} type="button" disabled={item.disabled} onClick={() => { item.action(); onClose(); }}>
              <span><strong>{item.label}</strong>{item.description && <small>{item.description}</small>}</span>{item.shortcut && <code>{item.shortcut}</code>}
            </button>
          ))}
          {!filtered.length && <p>No command matches this query.</p>}
        </div>
      </section>
    </div>
  );
}

