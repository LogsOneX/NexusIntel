import { useState } from "react";
import { Activity, Briefcase, ChevronDown, ChevronRight, Database, EyeOff, FileCheck, FolderOpen, Inbox, Network, Plus, PlusCircle, Radio, ShieldAlert, Trash2, X } from "lucide-react";
import type { ArtifactBinItem, CaseHealth, Investigation } from "../../lib/types";
import { caseTitle } from "../../lib/format";

function itemId(item: ArtifactBinItem, index: number) {
  return item.id || item.value || item.label || `item-${index}`;
}

function itemConfidence(item: ArtifactBinItem) {
  if (typeof item.confidence_score === "number") return `${Math.round(item.confidence_score)}%`;
  if (typeof item.confidence === "number") return `${Math.round(item.confidence)}%`;
  return String(item.confidence || "candidate");
}

function itemReason(item: ArtifactBinItem) {
  return item.confidence_reason || item.noise_reason || item.public_source_note || item.legal_basis || item.relationship || "Awaiting analyst review.";
}

export default function CaseDock({ investigations, activeCase, health, leads = [], noise = [], compliance = [], onSelect, onCreateBlank, onDeleteActive, onClearActive, onPromoteLead, onRestoreNoise, loading, onClose }: { investigations: Investigation[]; activeCase: Investigation | null; health: CaseHealth | null; leads?: ArtifactBinItem[]; noise?: ArtifactBinItem[]; compliance?: ArtifactBinItem[]; onSelect: (id: string) => void; onCreateBlank: () => void; onDeleteActive: () => void; onClearActive: () => void; onPromoteLead?: (id: string) => void; onRestoreNoise?: (id: string) => void; loading: boolean; onClose?: () => void }) {
  const [activeAccordion, setActiveAccordion] = useState<"candidates" | "noise" | "compliance" | null>(null);
  const score = health?.score ?? (activeCase ? 70 : 100);
  const risk = score < 45 ? "Critical" : score < 65 ? "High" : score < 82 ? "Medium" : "Low";
  const sourceCount = health ? Object.values(health.coverage || {}).filter((value) => value > 0).length : 0;
  const clusterCount = Math.max(0, Math.floor((health?.node_count || 0) / 3));
  const weakCount = health?.weak_nodes?.length || 0;
  const isolatedCount = health?.isolated_nodes?.length || 0;
  const evidenceQuality = health ? Math.max(0, Math.min(100, Math.round(score + sourceCount * 2 - weakCount * 4))) : 0;
  const reportReadiness = activeCase ? Math.max(0, Math.min(100, Math.round((score + evidenceQuality - noise.length * 2 - weakCount * 3) / 2))) : 0;
  const coverageGaps = health ? Object.entries(health.coverage || {}).filter(([, value]) => !value).map(([key]) => key).slice(0, 4) : [];
  const nextActions = health?.recommendations?.slice(0, 3) || [];
  const strongestPivots = health?.intelligence?.lead_queue?.slice(0, 3) || [];

  const toggleAccordion = (section: "candidates" | "noise" | "compliance") => setActiveAccordion((current) => current === section ? null : section);

  return (
    <aside className="graph-case-dock premium-case-dock reference-case-dock" aria-label="Investigation lifecycle controls">
      <header className="ref-dock-header">
        <div><Briefcase size={14} /><strong>Investigation Dock</strong></div>
        <div className="ref-dock-header-actions">
          <span>{activeCase ? activeCase.status : "Detached"}</span>
          {onClose && <button className="ref-panel-close" type="button" onClick={onClose} aria-label="Close case dock" title="Close"><X size={14} /></button>}
        </div>
      </header>

      <section className="ref-dock-context">
        <div className="ref-collab-row">
          <span><Radio size={11} />Collab: <b>Offline</b></span>
          <code>{activeCase ? "Case workspace" : "Detached Workspace"}</code>
        </div>
        <label>
          <span>Select Active Folder</span>
          <select aria-label="Select investigation" value={activeCase?.id || ""} onChange={(event) => onSelect(event.target.value)} disabled={loading}>
            <option value="">Detached Custom Workspace</option>
            {investigations.map((item) => <option value={item.id} key={item.id}>{caseTitle(item)} / {item.target_type}</option>)}
          </select>
        </label>
        <div className="ref-dock-actions">
          <button type="button" onClick={onCreateBlank} disabled={loading}><Plus size={12} />New Case</button>
          <button type="button" onClick={onClearActive} disabled={!activeCase || loading}><Database size={12} />Detach</button>
          <button className="danger" type="button" onClick={onDeleteActive} disabled={!activeCase || loading}><Trash2 size={12} />Delete</button>
        </div>
      </section>

      <section className="ref-dock-metrics">
        <div><span>Health <Activity size={10} /></span><strong>{score}%</strong><meter min="0" max="100" value={score} /></div>
        <div><span>Threat Risk <ShieldAlert size={10} /></span><strong className={risk === "Critical" || risk === "High" ? "risk-hot" : "risk-low"}>{risk}</strong><small>Evidence weighted</small></div>
        <div><span>Sources <Database size={10} /></span><strong>{sourceCount}</strong><small>Coverage domains</small></div>
        <div><span>Clusters <Network size={10} /></span><strong>{clusterCount}</strong><small>Graph components</small></div>
      </section>

      <section className="ref-dock-intel">
        <article>
          <span>Evidence Quality</span>
          <strong>{activeCase ? `${evidenceQuality}%` : "--"}</strong>
          <p>{activeCase ? `${weakCount} weak and ${isolatedCount} isolated entities need review.` : "Load a case to calculate evidence support."}</p>
        </article>
        <article>
          <span>Report Readiness</span>
          <strong>{activeCase ? `${reportReadiness}%` : "--"}</strong>
          <p>{activeCase ? "Weighted from health, evidence quality, noise, and weak findings." : "Awaiting case context."}</p>
        </article>
        <article>
          <span>Collection Gaps</span>
          {coverageGaps.length ? <ul>{coverageGaps.map((gap) => <li key={gap}>{gap}</li>)}</ul> : <p>{activeCase ? "No empty coverage domains reported." : "No case selected."}</p>}
        </article>
        <article>
          <span>Strongest Pivots</span>
          {strongestPivots.length ? <ul>{strongestPivots.map((pivot) => <li key={`${pivot.node_id}-${pivot.label}`}>{pivot.label || pivot.node_id}: {pivot.action}</li>)}</ul> : <p>No backend pivot recommendations yet.</p>}
        </article>
        <article className="wide">
          <span>Next Recommended Actions</span>
          {nextActions.length ? <ul>{nextActions.map((action) => <li key={`${action.priority}-${action.action}`}>{action.action}: {action.reason}</li>)}</ul> : <p>No backend recommendations yet. Run validation or a targeted transform to generate next actions.</p>}
        </article>
      </section>

      <section className="ref-dock-accordions">
        <div className="ref-accordion">
          <button type="button" onClick={() => toggleAccordion("candidates")}><span><Inbox size={12} />Candidate Leads</span><code>{leads.length}</code>{activeAccordion === "candidates" ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</button>
          {activeAccordion === "candidates" && <div className="ref-accordion-body">
            {leads.map((lead, index) => <article key={itemId(lead, index)} className="ref-bin-card">
              <div><span>{lead.type || lead.artifact_class || "candidate"}</span><code>{itemConfidence(lead)}</code></div>
              <strong>{lead.label || lead.value || "Candidate lead"}</strong>
              <p>{itemReason(lead)}</p>
              {onPromoteLead && <button type="button" onClick={() => onPromoteLead(String(lead.id || itemId(lead, index)))}><PlusCircle size={10} />Promote to Graph</button>}
            </article>)}
            {!leads.length && <p className="ref-empty-line">No candidate leads remaining.</p>}
          </div>}
        </div>

        <div className="ref-accordion">
          <button type="button" onClick={() => toggleAccordion("noise")}><span><EyeOff size={12} />Suppressed Noise</span><code>{noise.length}</code>{activeAccordion === "noise" ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</button>
          {activeAccordion === "noise" && <div className="ref-accordion-body">
            {noise.map((item, index) => <article key={itemId(item, index)} className="ref-bin-card compact">
              <div><span>{item.type || item.artifact_class || "noise"}</span></div>
              <strong>{item.label || item.value || "Suppressed artifact"}</strong>
              <p>{itemReason(item)}</p>
              {onRestoreNoise && <button type="button" onClick={() => onRestoreNoise(String(item.id || itemId(item, index)))}><PlusCircle size={10} />Restore</button>}
            </article>)}
            {!noise.length && <p className="ref-empty-line">No suppressed noise filters active.</p>}
          </div>}
        </div>

        <div className="ref-accordion">
          <button type="button" onClick={() => toggleAccordion("compliance")}><span><FileCheck size={12} />Compliance Audits</span><code>{compliance.length}</code>{activeAccordion === "compliance" ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</button>
          {activeAccordion === "compliance" && <div className="ref-accordion-body">
            <div className="ref-compliance-gate"><span>Security Guardrails</span><b>VERIFY</b></div>
            {compliance.map((item, index) => <article key={itemId(item, index)} className="ref-bin-card compact">
              <div><span>{item.type || item.artifact_class || "compliance"}</span><code>SECURE</code></div>
              <strong>{item.label || item.classification || "Policy note"}</strong>
              <p>{itemReason(item)}</p>
            </article>)}
            {!compliance.length && <p className="ref-empty-line">No compliance logs recorded.</p>}
          </div>}
        </div>
      </section>
    </aside>
  );
}
