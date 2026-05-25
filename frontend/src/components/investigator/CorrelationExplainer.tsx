import { Network } from "lucide-react";

type Correlation = { correlation_id?: string; type?: string; score?: number; reasons?: string[]; requires_analyst_confirmation?: boolean };

export default function CorrelationExplainer({ correlations }: { correlations?: Correlation[] | null }) {
  const items = correlations || [];
  return (
    <article className="investigator-card">
      <header><Network size={15} /><strong>Correlation Engine</strong><span>{items.length}</span></header>
      <div className="investigator-list compact">
        {items.slice(0, 6).map((item) => <div key={item.correlation_id || `${item.type}:${item.score}`}><strong>{item.type || "possible_same_actor"} / {item.score || 0}%</strong><span>{item.requires_analyst_confirmation ? "Analyst confirmation required" : "Context only"}</span><small>{(item.reasons || ["Weighted feature overlap."]).join("; ")}</small></div>)}
        {!items.length && <p className="empty-copy">No weighted correlations are available yet.</p>}
      </div>
    </article>
  );
}
