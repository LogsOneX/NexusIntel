import { GitBranch, Network, Orbit } from "lucide-react";

export default function GraphLayoutSelector({ onLayout }: { onLayout: (mode: "tree" | "circular" | "force") => void }) {
  return (
    <div className="graph-layout-selector" aria-label="Layout selector">
      <button type="button" onClick={() => onLayout("tree")} title="Tree layout"><GitBranch size={15} /><span>Tree</span></button>
      <button type="button" onClick={() => onLayout("circular")} title="Orbit layout"><Orbit size={15} /><span>Orbit</span></button>
      <button type="button" onClick={() => onLayout("force")} title="Force layout"><Network size={15} /><span>Force</span></button>
    </div>
  );
}
