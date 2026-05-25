import { useEffect, useMemo, useRef, useState } from "react";
import { ChevronRight, Command, HelpCircle, Search, X } from "lucide-react";
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
    <div className="command-palette-backdrop reference-command-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="command-palette reference-command-palette" role="dialog" aria-modal="true" aria-label="Command palette" onMouseDown={(event) => event.stopPropagation()}>
        <header className="ref-command-searchbar">
          <Command size={16} />
          <label>
            <Search size={14} />
            <input ref={inputRef} value={query} onChange={(event) => { setQuery(event.target.value); setIndex(0); }} placeholder="Type command name to execute action..." />
          </label>
          <span>ESC to cancel</span>
          <button type="button" onClick={onClose} aria-label="Close command palette"><X size={14} /></button>
        </header>
        <div className="palette-results ref-command-results">
          {filtered.map((item, itemIndex) => (
            <button className={itemIndex === index ? "active" : ""} key={item.id} type="button" disabled={item.disabled} onClick={() => { item.action(); onClose(); }}>
              <i><Command size={14} /></i>
              <span><strong>{item.label}<em>{item.group || "COMMAND"}</em></strong>{item.description && <small>{item.description}</small>}</span>
              <b>{item.shortcut && <code>{item.shortcut}</code>}{itemIndex === index && <ChevronRight size={13} />}</b>
            </button>
          ))}
          {!filtered.length && <p><HelpCircle size={24} /><strong>No matching operators found</strong><small>Refine the command or workflow search term.</small></p>}
        </div>
        <footer className="ref-command-footer"><span>up/down to select</span><span>enter to run</span><span>NexusIntel operator suite</span></footer>
      </section>
    </div>
  );
}
