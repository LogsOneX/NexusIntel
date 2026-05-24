import { useMemo, useState } from "react";
import { Database, Filter } from "lucide-react";
import type { EvidenceRecord, GraphPayload } from "../../lib/types";
import { deriveEvidenceFromGraph } from "../../lib/graph";
import EmptyState from "../common/EmptyState";
import EvidenceCard from "./EvidenceCard";

export default function EvidenceBrowser({ evidence = [], graph, investigationId, onOpenRaw }: { evidence?: EvidenceRecord[]; graph?: GraphPayload | null; investigationId?: string | null; onOpenRaw?: (id: string) => void }) {
  const [query, setQuery] = useState("");
  const rows = useMemo(() => {
    const combined = evidence.length ? evidence : deriveEvidenceFromGraph(graph || { nodes: [], edges: [] }, investigationId || "local");
    const term = query.trim().toLowerCase();
    return combined.filter((item) => !term || `${item.source} ${item.uri} ${item.sha256} ${item.content_type}`.toLowerCase().includes(term));
  }, [evidence, graph, investigationId, query]);
  return (
    <section className="evidence-browser">
      <header><div><Database size={15} /><strong>Evidence Browser</strong></div><label><Filter size={14} /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter source, hash, URL" /></label></header>
      {!rows.length ? <EmptyState title="No evidence collected" message="Evidence appears after an adapter stores source URL, timestamp, hash, and legal note. No demo evidence is generated." icon={Database} /> : <div className="evidence-list">{rows.map((item) => <EvidenceCard evidence={item} key={item.id} onOpenRaw={onOpenRaw} />)}</div>}
    </section>
  );
}

