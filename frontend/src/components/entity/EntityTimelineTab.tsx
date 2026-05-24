import { Clock3 } from "lucide-react";
import type { ApiNode, EvidenceRecord } from "../../lib/types";
import { formatDate } from "../../lib/format";
import EmptyState from "../common/EmptyState";

export default function EntityTimelineTab({ node, evidence }: { node: ApiNode | null; evidence: EvidenceRecord[] }) {
  const events = [
    ...(node?.created_at ? [{ time: node.created_at, label: "Node created", detail: node.label }] : []),
    ...evidence.map((item) => ({ time: item.created_at, label: `Evidence captured: ${item.source}`, detail: item.sha256 })),
  ].sort((a, b) => Date.parse(a.time) - Date.parse(b.time));
  if (!events.length) return <EmptyState title="No entity timeline" message="Evidence timestamps and transform runs appear here once collected." icon={Clock3} />;
  return <div className="entity-timeline">{events.map((item, index) => <article key={`${item.time}-${index}`}><span>{formatDate(item.time)}</span><strong>{item.label}</strong><code>{item.detail}</code></article>)}</div>;
}

