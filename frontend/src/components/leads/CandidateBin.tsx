import { ExternalLink, GitBranch, ShieldAlert, UploadCloud } from "lucide-react";
import type { ArtifactBinItem } from "../../lib/types";

function labelFor(item: ArtifactBinItem): string {
  return String(item.label || item.value || item.type || "candidate");
}

export default function CandidateBin({ items = [], onPromote, onMarkNoise }: { items?: ArtifactBinItem[]; onPromote?: (id: string) => void; onMarkNoise?: (id: string) => void }) {
  return (
    <section className="artifact-bin candidate-bin" aria-label="Candidate leads">
      <header><GitBranch size={13} /><strong>Candidate Bin</strong><span>{items.length}</span></header>
      {!items.length ? <p>No candidate leads are suppressed right now. Verified entities remain on the main graph.</p> : (
        <div>
          {items.slice(0, 8).map((item, index) => {
            const id = item.id || `${item.type || "candidate"}:${item.value || index}`;
            return (
              <article key={id}>
                <strong>{labelFor(item)}</strong>
                <span>{item.type || "candidate"} / {item.source || "unknown source"}</span>
                {item.confidence_reason && <p>{item.confidence_reason}</p>}
                <footer>
                  {item.source_url && <a href={String(item.source_url)} target="_blank" rel="noreferrer"><ExternalLink size={12} />Source</a>}
                  {onPromote && <button type="button" onClick={() => onPromote(id)}><UploadCloud size={12} />Promote</button>}
                  {onMarkNoise && <button className="danger" type="button" onClick={() => onMarkNoise(id)}><ShieldAlert size={12} />Noise</button>}
                </footer>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
