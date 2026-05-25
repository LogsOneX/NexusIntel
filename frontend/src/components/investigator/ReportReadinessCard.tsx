import { FileCheck2 } from "lucide-react";

type Readiness = { score?: number; blockers?: string[]; warnings?: string[]; recommended_actions?: string[]; attribution_risk?: string };

export default function ReportReadinessCard({ readiness }: { readiness?: Readiness | null }) {
  return (
    <article className="investigator-card report-readiness-card">
      <header><FileCheck2 size={15} /><strong>Report Readiness</strong><span>{readiness?.score ?? 0}%</span></header>
      <div className="readiness-bar"><i style={{ width: `${Math.max(0, Math.min(100, readiness?.score ?? 0))}%` }} /></div>
      <div className="investigator-list compact">
        {(readiness?.blockers || []).slice(0, 3).map((item) => <div key={item}><strong>Blocker</strong><small>{item}</small></div>)}
        {(readiness?.warnings || []).slice(0, 3).map((item) => <div key={item}><strong>Warning</strong><small>{item}</small></div>)}
        {!readiness?.blockers?.length && !readiness?.warnings?.length && <p className="empty-copy">No readiness blockers reported.</p>}
      </div>
    </article>
  );
}
