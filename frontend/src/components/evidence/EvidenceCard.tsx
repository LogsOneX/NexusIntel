import { Copy, Database, ExternalLink, FileJson } from "lucide-react";
import type { EvidenceRecord } from "../../lib/types";
import { formatDate } from "../../lib/format";
import StatusChip from "../common/StatusChip";

export default function EvidenceCard({ evidence, onOpenRaw }: { evidence: EvidenceRecord; onOpenRaw?: (id: string) => void }) {
  const copy = (value: string) => void navigator.clipboard?.writeText(value).catch(() => undefined);
  return (
    <article className="evidence-card">
      <header><Database size={14} /><strong>{evidence.source}</strong><StatusChip label={evidence.content_type || "raw"} tone="info" /></header>
      <p>{evidence.uri}</p>
      <div className="evidence-meta"><span>fetched {formatDate(evidence.created_at)}</span><code>{evidence.sha256}</code></div>
      <footer>
        {evidence.uri?.startsWith("http") && <a href={evidence.uri} target="_blank" rel="noreferrer"><ExternalLink size={13} />Source</a>}
        <button type="button" onClick={() => copy(evidence.uri)}><Copy size={13} />URL</button>
        <button type="button" onClick={() => copy(evidence.sha256)}><Copy size={13} />Hash</button>
        {onOpenRaw && <button type="button" onClick={() => onOpenRaw(evidence.id)}><FileJson size={13} />Raw</button>}
      </footer>
    </article>
  );
}

