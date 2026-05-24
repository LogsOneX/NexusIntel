import { Activity, Database, ShieldCheck } from "lucide-react";
import type { ApiNode, AnalystPipeline, Investigation, TransformDefinition } from "../../lib/types";
import { caseTitle, formatDate, safeString } from "../../lib/format";
import StatusChip from "../common/StatusChip";
import MetricCard from "../common/MetricCard";
import ConfidenceExplainer from "./ConfidenceExplainer";

export default function EntityOverviewTab({ node, activeCase, analystPipeline, pendingEntityType, pendingTransforms }: { node: ApiNode | null; activeCase?: Investigation | null; analystPipeline?: AnalystPipeline | null; pendingEntityType?: string; pendingTransforms?: TransformDefinition[] }) {
  if (!node) {
    return (
      <div className="entity-overview-grid">
        <MetricCard label="Pending Type" value={pendingEntityType || "unknown"} detail="no lookup will run automatically" icon={Activity} />
        <MetricCard label="Available" value={pendingTransforms?.filter((item) => item.enabled).length || 0} detail="transforms" icon={ShieldCheck} />
        <p className="muted-copy">Add the entity to the graph first, then choose a transform. Empty state only; no synthetic intelligence is created.</p>
      </div>
    );
  }
  const data = node.data || {};
  const artifact = (data.artifact || {}) as Record<string, unknown>;
  return (
    <div className="entity-overview-grid">
      <div className="entity-hero">
        <strong>{node.label}</strong>
        <code>{node.type} / {node.confidence || "medium"}</code>
        <div><StatusChip label={safeString(node.source, "source pending")} tone="info" /><StatusChip label={caseTitle(activeCase)} tone="muted" /></div>
      </div>
      <div className="entity-meta-grid">
        <MetricCard label="Type" value={node.type} icon={Activity} />
        <MetricCard label="Source" value={safeString(node.source)} icon={Database} />
        <MetricCard label="First Seen" value={formatDate(node.created_at)} icon={Activity} />
        <MetricCard label="Evidence" value={safeString(data.raw_evidence_ref || artifact.raw_evidence_ref, "pending")} icon={Database} />
      </div>
      <ConfidenceExplainer node={node} analystPipeline={analystPipeline} />
      <section className="legal-note"><strong>Legal/Public Source Note</strong><p>{safeString(data.legal_basis || data.legal_note || artifact.legal_basis || analystPipeline?.selected_entity?.legal_note, "No legal note recorded yet. Run evidence-backed adapters to attach source notes.")}</p></section>
    </div>
  );
}

