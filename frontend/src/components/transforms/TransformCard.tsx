import { Play, ShieldCheck, Timer } from "lucide-react";
import type { ApiNode, TransformDefinition } from "../../lib/types";
import { transformMatchesEntity } from "../../lib/transformMatching";
import StatusChip from "../common/StatusChip";

export default function TransformCard({ transform, selectedNode, onRun, loading }: { transform: TransformDefinition; selectedNode?: ApiNode | null; onRun?: (id: string) => void; loading?: boolean }) {
  const compatible = !selectedNode || transformMatchesEntity(transform, selectedNode.type);
  const disabledReason = !compatible ? `Requires ${transform.input_types.join(", ")}` : !transform.enabled ? transform.disabled_reason || "Disabled" : "";
  return (
    <article className={compatible && transform.enabled ? "transform-card" : "transform-card disabled"}>
      <header><strong>{transform.label}</strong><div>{transform.source_category === "fallback" && <StatusChip label="fallback" tone="warning" />}{transform.requires_api_key && <StatusChip label="API key" tone="key" />}{transform.passive !== false && <StatusChip label="passive" tone="ok" />}</div></header>
      <p>{transform.description}</p>
      <div className="transform-meta"><span><ShieldCheck size={12} />{transform.confidence_profile || "evidence-scored"}</span><span><Timer size={12} />{transform.estimated_runtime || "variable"}</span></div>
      <code>{transform.input_types.join(", ")} {"->"} {transform.output_types.join(", ")}</code>
      {disabledReason && <small>{disabledReason}</small>}
      {onRun && <button type="button" disabled={loading || Boolean(disabledReason)} onClick={() => onRun(transform.id)}><Play size={13} />{loading ? "Running" : "Run"}</button>}
    </article>
  );
}
