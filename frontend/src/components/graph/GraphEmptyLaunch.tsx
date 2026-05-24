import { AtSign, Database, FileInput, Globe, Phone, UserRound } from "lucide-react";

export default function GraphEmptyLaunch({ hasCase, onAdd, onOpenDock, onOpenPalette }: { hasCase: boolean; onAdd: (value: string) => void; onOpenDock: () => void; onOpenPalette: () => void }) {
  const seed = (kind: string) => {
    const value = window.prompt(`Seed ${kind}`);
    if (value?.trim()) onAdd(value.trim());
  };
  return (
    <section className="graph-empty-launch" aria-label="Start link analysis">
      <span className="micro-label">Link analysis</span>
      <h2>{hasCase ? "Case graph is empty" : "Start a Link Analysis"}</h2>
      <p>Add a seed entity, run a lookup, or import public evidence. No demo intelligence is inserted here.</p>
      <div className="empty-launch-actions">
        <button type="button" onClick={() => seed("username")}><UserRound size={15} />Add Username</button>
        <button type="button" onClick={() => seed("email")}><AtSign size={15} />Add Email</button>
        <button type="button" onClick={() => seed("domain")}><Globe size={15} />Add Domain</button>
        <button type="button" onClick={() => seed("phone")}><Phone size={15} />Add Phone</button>
        <button type="button" onClick={onOpenPalette}><Database size={15} />Entity Palette</button>
        <button type="button"><FileInput size={15} />Import CSV/JSON</button>
      </div>
      <footer><kbd>Ctrl K</kbd><span>Command</span><kbd>/</kbd><span>Search</span><kbd>D</kbd><span>Case Dock</span><kbd>I</kbd><span>Inspector</span></footer>
    </section>
  );
}
