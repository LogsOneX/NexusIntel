import { FilterX } from "lucide-react";

type NoiseItem = { noise_score?: number; reasons?: string[]; recommended_action?: string; affected_node_ids?: string[]; is_noise?: boolean };

export default function NoiseExplanationPanel({ noise }: { noise?: { removed_count?: number; items?: NoiseItem[] } | null }) {
  const items = (noise?.items || []).filter((item) => item.is_noise).slice(0, 6);
  return (
    <article className="investigator-card">
      <header><FilterX size={15} /><strong>Noise Removed</strong><span>{noise?.removed_count || 0}</span></header>
      <div className="investigator-list compact">
        {items.length ? items.map((item, index) => (
          <div key={`${item.noise_score}:${index}`}>
            <strong>{item.recommended_action || "suppress"}</strong>
            <span>{item.noise_score || 0}% noise</span>
            <small>{(item.reasons || ["Noise marker detected."]).join("; ")}</small>
          </div>
        )) : <p className="empty-copy">No suppressed noise is reported for the current case.</p>}
      </div>
    </article>
  );
}
