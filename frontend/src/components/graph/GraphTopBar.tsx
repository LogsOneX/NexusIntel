import { Database, Download, FolderOpen, MoreHorizontal, PanelBottom, PanelLeft, PanelRight, Plus, Radio, Search } from "lucide-react";
import { FormEvent, useState } from "react";
import type { Investigation } from "../../lib/types";
import { caseTitle } from "../../lib/format";
import GraphLayoutSelector from "./GraphLayoutSelector";
import GraphMoreMenu from "./GraphMoreMenu";

type Mode = "passive" | "standard" | "aggressive";

export default function GraphTopBar({ activeCase, entities, relationships, target, setTarget, detectedType, mode, setMode, loading, dockOpen = false, inspectorOpen = false, terminalOpen = false, paletteOpen = false, onLookup, onAddEntity, onOpenPalette, onToggleDock, onToggleInspector, onToggleTerminal, onExport, onFit, onLayout, onOpenEvidence, onOpenInvestigator, onReviewNoise, onOpenSettings }: { activeCase: Investigation | null; entities: number; relationships: number; target: string; setTarget: (value: string) => void; detectedType: string; mode: Mode; setMode: (mode: Mode) => void; loading: boolean; dockOpen?: boolean; inspectorOpen?: boolean; terminalOpen?: boolean; paletteOpen?: boolean; onLookup: (event: FormEvent<HTMLFormElement>) => void | Promise<void>; onAddEntity: () => void; onOpenPalette: () => void; onToggleDock: () => void; onToggleInspector: () => void; onToggleTerminal: () => void; onExport: () => void; onFit: () => void; onLayout: (mode: "tree" | "circular" | "force") => void; onOpenEvidence?: () => void; onOpenInvestigator?: () => void; onReviewNoise?: () => void; onOpenSettings?: () => void }) {
  const [moreOpen, setMoreOpen] = useState(false);
  return (
    <header className="nexus-commandbar graph-topbar-v2">
      <section className="topbar-left">
        <div className="graph-product-label"><strong>NexusIntel</strong><span>/ Graph</span></div>
        <button className="case-chip" type="button" onClick={onToggleDock}><FolderOpen size={14} /><span>{activeCase ? caseTitle(activeCase) : "Detached"}</span></button>
        <div className="graph-stats-chip"><strong>{entities}</strong><span>entities</span><strong>{relationships}</strong><span>links</span></div>
      </section>
      <form className="nexus-commandbar-center topbar-center" onSubmit={onLookup}>
        <label className="graph-search-field"><Search size={15} /><input value={target} onChange={(event) => setTarget(event.target.value)} placeholder="Search or enter seed entity" /></label>
        <span className="entity-detect-chip">{detectedType}</span>
        <select value={mode} onChange={(event) => setMode(event.target.value as Mode)} aria-label="Recon mode"><option value="passive">Passive</option><option value="standard">Standard</option><option value="aggressive">Deep</option></select>
        <button className="primary" type="submit" disabled={loading || !target.trim()}><Radio size={14} />Lookup</button>
        <button type="button" onClick={onAddEntity}><Plus size={14} />Add Entity</button>
      </form>
      <section className="topbar-right">
        <button type="button" onClick={onOpenPalette} data-active={paletteOpen || undefined}><Database size={14} /><span>Palette</span></button>
        <GraphLayoutSelector onLayout={onLayout} />
        <button className="icon-only" type="button" onClick={onToggleDock} title="Toggle case dock" data-active={dockOpen || undefined}><PanelLeft size={15} /></button>
        <button className="icon-only" type="button" onClick={onToggleInspector} title="Toggle inspector" data-active={inspectorOpen || undefined}><PanelRight size={15} /></button>
        <button className="icon-only" type="button" onClick={onToggleTerminal} title="Toggle telemetry" data-active={terminalOpen || undefined}><PanelBottom size={15} /></button>
        <button className="export-button" type="button" onClick={onExport}><Download size={14} /><span>Export</span></button>
        <div className="more-menu-wrap"><button className="icon-only" type="button" onClick={() => setMoreOpen((open) => !open)} title="More actions"><MoreHorizontal size={16} /></button><GraphMoreMenu open={moreOpen} onFit={onFit} onToggleDock={onToggleDock} onToggleInspector={onToggleInspector} onToggleTerminal={onToggleTerminal} onExport={onExport} onOpenEvidence={onOpenEvidence} onOpenInvestigator={onOpenInvestigator} onReviewNoise={onReviewNoise} onOpenSettings={onOpenSettings} /></div>
      </section>
    </header>
  );
}
