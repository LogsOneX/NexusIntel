import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { ApiNode, AnalystPipeline } from "../../lib/types";
import { confidenceForNode, confidenceLabel, evidenceWarning } from "../../lib/confidence";
import StatusChip from "../common/StatusChip";

export default function ConfidenceExplainer({ node, analystPipeline }: { node: ApiNode | null; analystPipeline?: AnalystPipeline | null }) {
  const baseline = analystPipeline?.selected_entity?.confidence_baseline;
  const score = typeof baseline === "number" ? baseline : confidenceForNode(node);
  const warning = evidenceWarning(node);
  const reason = analystPipeline?.selected_entity?.confidence_reason || String(node?.data?.confidence_reason || node?.data?.confidence_note || "Confidence is inferred from available public evidence and source reliability.");
  return (
    <section className="confidence-explainer">
      <header><CheckCircle2 size={14} /><strong>Confidence</strong><StatusChip label={`${score}% ${confidenceLabel(score)}`} tone={score >= 80 ? "ok" : score >= 50 ? "warning" : "muted"} /></header>
      <p>{reason}</p>
      {warning && <div className="evidence-warning"><AlertTriangle size={13} />{warning}</div>}
    </section>
  );
}

