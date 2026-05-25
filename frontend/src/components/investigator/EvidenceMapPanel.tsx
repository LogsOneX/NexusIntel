import { FileSearch } from "lucide-react";

type EvidenceMap = { evidence_count?: number; coverage?: Record<string, number>; unsupported_findings?: Array<Record<string, any>> };

export default function EvidenceMapPanel({ evidenceMap }: { evidenceMap?: EvidenceMap | null }) {
  const coverage = evidenceMap?.coverage || {};
  const unsupported = evidenceMap?.unsupported_findings || [];
  return (
    <article className="investigator-card">
      <header><FileSearch size={15} /><strong>Evidence Map</strong><span>{evidenceMap?.evidence_count || 0} objects</span></header>
      <div className="investigator-counts">
        <span>Supported nodes<b>{coverage.supported_nodes || 0}</b></span>
        <span>Supported edges<b>{coverage.supported_edges || 0}</b></span>
        <span>Unsupported<b>{coverage.unsupported || 0}</b></span>
      </div>
      <div className="investigator-list compact">
        {unsupported.slice(0, 5).map((item, index) => <div key={`${item.id || index}`}><strong>{item.label || item.id || "Unsupported finding"}</strong><small>{item.warning || "No evidence link found."}</small></div>)}
        {!unsupported.length && <p className="empty-copy">No unsupported finding warnings reported.</p>}
      </div>
    </article>
  );
}
