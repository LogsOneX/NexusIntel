import { Activity, Database, FolderOpen, Plus, Trash2 } from "lucide-react";
import type { ArtifactBinItem, CaseHealth, Investigation } from "../../lib/types";
import { caseTitle } from "../../lib/format";
import CaseHealthCard from "./CaseHealthCard";
import CandidateBin from "../leads/CandidateBin";
import NoiseBin from "../noise/NoiseBin";
import ComplianceLog from "../compliance/ComplianceLog";

export default function CaseDock({ investigations, activeCase, health, leads = [], noise = [], compliance = [], onSelect, onCreateBlank, onDeleteActive, onClearActive, onPromoteLead, onRestoreNoise, loading }: { investigations: Investigation[]; activeCase: Investigation | null; health: CaseHealth | null; leads?: ArtifactBinItem[]; noise?: ArtifactBinItem[]; compliance?: ArtifactBinItem[]; onSelect: (id: string) => void; onCreateBlank: () => void; onDeleteActive: () => void; onClearActive: () => void; onPromoteLead?: (id: string) => void; onRestoreNoise?: (id: string) => void; loading: boolean }) {
  return (
    <aside className="graph-case-dock premium-case-dock" aria-label="Investigation lifecycle controls">
      <header><div><FolderOpen size={14} /><strong>Investigation</strong></div><span>{activeCase ? activeCase.status : "detached"}</span></header>
      <select aria-label="Select investigation" value={activeCase?.id || ""} onChange={(event) => onSelect(event.target.value)} disabled={loading}>
        <option value="">No case selected</option>
        {investigations.map((item) => <option value={item.id} key={item.id}>{caseTitle(item)} / {item.target_type}</option>)}
      </select>
      <div className="case-dock-actions">
        <button type="button" onClick={onCreateBlank} disabled={loading} title="Create a blank investigation"><Plus size={13} />New</button>
        <button type="button" onClick={onClearActive} disabled={!activeCase || loading} title="Detach graph without deleting"><Database size={13} />Clear</button>
        <button className="danger" type="button" onClick={onDeleteActive} disabled={!activeCase || loading} title="Delete this investigation"><Trash2 size={13} />Delete</button>
      </div>
      <div className="case-health-strip"><span><Activity size={13} />Health {health ? `${health.score}%` : "--"}</span><code>{health?.status || "no graph"}</code></div>
      <CaseHealthCard health={health} />
      <CandidateBin items={leads} onPromote={onPromoteLead} />
      <NoiseBin items={noise} onRestore={onRestoreNoise} />
      <ComplianceLog items={compliance} />
    </aside>
  );
}

