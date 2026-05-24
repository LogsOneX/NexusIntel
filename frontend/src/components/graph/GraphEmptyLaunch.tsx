import { AtSign, Database, FileInput, Globe, Phone, UserRound } from "lucide-react";

export default function GraphEmptyLaunch({ hasCase, onOpenAdd, onOpenDock, onOpenPalette }: { hasCase: boolean; onOpenAdd: (kind: string) => void; onOpenDock: () => void; onOpenPalette: () => void }) {
  return (
    <section className="graph-empty-launch" aria-label="Start link analysis">
      <span className="micro-label">Link analysis</span>
      <h2>{hasCase ? "Case graph is empty" : "Start a Link Analysis"}</h2>
      <p>Add a seed entity, run a lookup, or import public evidence. No demo intelligence is inserted here.</p>
      <div className="empty-launch-actions">
        <button type="button" onClick={() => onOpenAdd("username")}><UserRound size={15} />Add Username</button>
        <button type="button" onClick={() => onOpenAdd("email")}><AtSign size={15} />Add Email</button>
        <button type="button" onClick={() => onOpenAdd("domain")}><Globe size={15} />Add Domain</button>
        <button type="button" onClick={() => onOpenAdd("phone")}><Phone size={15} />Add Phone</button>
        <button type="button" onClick={onOpenPalette}><Database size={15} />Entity Palette</button>
        <button type="button" onClick={onOpenDock}><FileInput size={15} />Open Case Dock</button>
      </div>
      <footer><kbd>Ctrl K</kbd><span>Command</span><kbd>/</kbd><span>Search</span><kbd>D</kbd><span>Case Dock</span><kbd>I</kbd><span>Inspector</span></footer>
    </section>
  );
}
