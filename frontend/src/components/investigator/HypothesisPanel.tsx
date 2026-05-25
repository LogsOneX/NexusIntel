import { GitMerge } from "lucide-react";

type Hypothesis = { hypothesis_id?: string; statement?: string; status?: string; confidence_score?: number; confidence_reason?: string; analyst_warning?: string; next_tests?: string[] };

export default function HypothesisPanel({ hypotheses }: { hypotheses?: Hypothesis[] | null }) {
  const items = hypotheses || [];
  return (
    <article className="investigator-card">
      <header><GitMerge size={15} /><strong>Hypotheses</strong><span>{items.length}</span></header>
      <div className="investigator-list">
        {items.slice(0, 5).map((item) => (
          <div key={item.hypothesis_id || item.statement}>
            <strong>{item.statement || "Hypothesis pending"}</strong>
            <span>{item.status || "proposed"} / {item.confidence_score || 0}%</span>
            <small>{item.confidence_reason || item.analyst_warning || "Requires corroborating evidence."}</small>
          </div>
        ))}
        {!items.length && <p className="empty-copy">No active hypotheses. Run validation or collect more direct evidence.</p>}
      </div>
    </article>
  );
}
