import { ShieldAlert } from "lucide-react";

export default function NoiseReviewPanel({ noise }: { noise?: { items?: Array<Record<string, any>> } | null }) {
  const items = (noise?.items || []).slice(0, 8);
  return (
    <article className="investigator-card">
      <header><ShieldAlert size={15} /><strong>Noise Review</strong><span>{items.length}</span></header>
      <div className="investigator-list compact">
        {items.map((item, index) => <div key={`${item.noise_score || 0}:${index}`}><strong>{String(item.recommended_action || "review")}</strong><span>{String(item.noise_score || 0)}% noise score</span><small>{Array.isArray(item.reasons) ? item.reasons.join("; ") : "Noise classifier output."}</small></div>)}
        {!items.length && <p className="empty-copy">No noise items pending review.</p>}
      </div>
    </article>
  );
}
