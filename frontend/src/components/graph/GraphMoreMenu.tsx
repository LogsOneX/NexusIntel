import { BrainCircuit, Database, Download, EyeOff, Filter, Maximize2, PanelBottom, PanelLeft, PanelRight, Settings } from "lucide-react";

export default function GraphMoreMenu({ open, onFit, onToggleDock, onToggleInspector, onToggleTerminal, onExport, onOpenEvidence, onOpenInvestigator, onReviewNoise, onOpenSettings }: { open: boolean; onFit: () => void; onToggleDock: () => void; onToggleInspector: () => void; onToggleTerminal: () => void; onExport: () => void; onOpenEvidence?: () => void; onOpenInvestigator?: () => void; onReviewNoise?: () => void; onOpenSettings?: () => void }) {
  if (!open) return null;
  return (
    <div className="graph-more-menu" role="menu">
      <button type="button" onClick={onOpenInvestigator}><BrainCircuit size={14} />Investigator</button>
      <button type="button" onClick={onOpenEvidence}><Database size={14} />Evidence Vault</button>
      <button type="button" onClick={onFit}><Maximize2 size={14} />Fit graph</button>
      <button type="button" onClick={onToggleDock}><PanelLeft size={14} />Case dock</button>
      <button type="button" onClick={onToggleInspector}><PanelRight size={14} />Inspector</button>
      <button type="button" onClick={onToggleTerminal}><PanelBottom size={14} />Telemetry</button>
      <button type="button" onClick={onReviewNoise}><EyeOff size={14} />Review noise</button>
      <button type="button"><Filter size={14} />Filters</button>
      <button type="button" onClick={onOpenSettings}><Settings size={14} />Connector status</button>
      <button type="button" onClick={onExport}><Download size={14} />Export</button>
    </div>
  );
}
