import { Download, Filter, Maximize2, PanelBottom, PanelLeft, PanelRight } from "lucide-react";

export default function GraphMoreMenu({ open, onFit, onToggleDock, onToggleInspector, onToggleTerminal, onExport }: { open: boolean; onFit: () => void; onToggleDock: () => void; onToggleInspector: () => void; onToggleTerminal: () => void; onExport: () => void }) {
  if (!open) return null;
  return (
    <div className="graph-more-menu" role="menu">
      <button type="button" onClick={onFit}><Maximize2 size={14} />Fit graph</button>
      <button type="button" onClick={onToggleDock}><PanelLeft size={14} />Case dock</button>
      <button type="button" onClick={onToggleInspector}><PanelRight size={14} />Inspector</button>
      <button type="button" onClick={onToggleTerminal}><PanelBottom size={14} />Telemetry</button>
      <button type="button"><Filter size={14} />Filters</button>
      <button type="button" onClick={onExport}><Download size={14} />Export</button>
    </div>
  );
}
