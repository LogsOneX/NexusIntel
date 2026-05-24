import { ShieldCheck } from "lucide-react";
import type { ArtifactBinItem } from "../../lib/types";

function labelFor(item: ArtifactBinItem): string {
  return String(item.label || item.value || item.type || "compliance artifact");
}

export default function ComplianceLog({ items = [] }: { items?: ArtifactBinItem[] }) {
  return (
    <section className="artifact-bin compliance-log" aria-label="Compliance log">
      <header><ShieldCheck size={13} /><strong>Compliance Log</strong><span>{items.length}</span></header>
      {!items.length ? <p>No compliance notices captured. Policy artifacts never become graph entities.</p> : (
        <div>
          {items.slice(0, 8).map((item, index) => (
            <article key={item.id || `${item.type || "compliance"}:${item.value || index}`}>
              <strong>{labelFor(item)}</strong>
              <span>{item.relationship || item.type || "policy"}</span>
              {(item.legal_basis || item.public_source_note) && <p>{item.legal_basis || item.public_source_note}</p>}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
