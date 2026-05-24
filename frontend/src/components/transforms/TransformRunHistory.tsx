import { Clock3 } from "lucide-react";

export type TransformRun = { id: string; transform: string; node_id?: string; status: string; created_at: string };

export default function TransformRunHistory({ runs = [] }: { runs?: TransformRun[] }) {
  return <section className="transform-history"><header><Clock3 size={14} /><strong>Run History</strong></header>{runs.length ? runs.map((run) => <div key={run.id}><span>{new Date(run.created_at).toLocaleString()}</span><strong>{run.transform}</strong><code>{run.status}</code></div>) : <p>No local run history for this node yet.</p>}</section>;
}

