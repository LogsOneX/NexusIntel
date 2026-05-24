import { Database, RotateCcw } from "lucide-react";
import type { ArtifactBinItem } from "../../lib/types";

function labelFor(item: ArtifactBinItem): string {
  return String(item.label || item.value || item.type || "noise");
}

export default function NoiseBin({ items = [], onRestore }: { items?: ArtifactBinItem[]; onRestore?: (id: string) => void }) {
  return (
    <section className="artifact-bin noise-bin" aria-label="Noise filtered">
      <header><Database size={13} /><strong>Noise Bin</strong><span>{items.length}</span></header>
      {!items.length ? <p>No suppressed noise. Generic/login/auth-wall artifacts stay out of the graph.</p> : (
        <div>
          {items.slice(0, 8).map((item, index) => {
            const id = item.id || `${item.type || "noise"}:${item.value || index}`;
            return (
              <article key={id}>
                <strong>{labelFor(item)}</strong>
                <span>{item.type || "noise"} / {item.source || "unknown source"}</span>
                {(item.noise_reason || item.confidence_reason) && <p>{item.noise_reason || item.confidence_reason}</p>}
                {onRestore && <footer><button type="button" onClick={() => onRestore(id)}><RotateCcw size={12} />Restore</button></footer>}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
