import { Copy } from "lucide-react";
import type { ApiNode } from "../../lib/types";
import { flattenData } from "../../lib/graph";
import EmptyState from "../common/EmptyState";

export default function EntityRawTab({ node }: { node: ApiNode | null }) {
  if (!node) return <EmptyState title="No raw node selected" />;
  const rows = flattenData({ id: node.id, type: node.type, label: node.label, value: node.value, source: node.source || "unknown", confidence: node.confidence || "medium", created_at: node.created_at || "", data: node.data || {} });
  const copy = () => void navigator.clipboard?.writeText(JSON.stringify(node, null, 2)).catch(() => undefined);
  return <section className="entity-raw"><header><strong>Raw Entity JSON</strong><button type="button" onClick={copy}><Copy size={13} />Copy JSON</button></header><div className="nx-data-table">{rows.map(([key, value]) => <div className="nx-row" key={`${key}:${value}`}><span>{key}</span><code>{value}</code></div>)}</div><pre>{JSON.stringify(node, null, 2)}</pre></section>;
}

