import { Crosshair, GitBranch, ShieldAlert } from "lucide-react";
import type { AnalystPipeline, CaseHealth } from "../../lib/types";
import EmptyState from "../common/EmptyState";
import StatusChip from "../common/StatusChip";

function leadLabel(item: Record<string, unknown>) {
  return String(item.label || item.action || item.node_id || item.reason || "Untitled lead");
}

export default function LeadQueuePanel({ analystPipeline, health, compact = false }: { analystPipeline?: AnalystPipeline | null; health?: CaseHealth | null; compact?: boolean }) {
  const sections = [
    { id: "strong", title: "Strongest Pivots", icon: Crosshair, items: analystPipeline?.lead_queue?.strongest_pivots || health?.intelligence?.lead_queue || [] },
    { id: "same", title: "Possible Same Actor", icon: GitBranch, items: analystPipeline?.lead_queue?.possible_same_actor_links || [] },
    { id: "contra", title: "Contradictions", icon: ShieldAlert, items: analystPipeline?.lead_queue?.contradictions || [] },
    { id: "next", title: "Next Actions", icon: Crosshair, items: analystPipeline?.lead_queue?.high_value_next_actions || health?.recommendations || [] },
  ];
  const total = sections.reduce((count, section) => count + section.items.length, 0);
  if (!total) return <EmptyState title="No active leads" message="Run evidence-backed transforms to build a lead queue. No placeholder intelligence is inserted here." icon={Crosshair} />;
  return (
    <section className={compact ? "lead-queue compact" : "lead-queue"}>
      {sections.map((section) => {
        const Icon = section.icon;
        if (!section.items.length) return null;
        return (
          <div key={section.id}>
            <header><Icon size={14} /><strong>{section.title}</strong><StatusChip label={`${section.items.length}`} tone={section.id === "contra" ? "warning" : "info"} /></header>
            {section.items.slice(0, compact ? 3 : 6).map((item, index) => (
              <article className="lead-item" key={`${section.id}-${index}`}>
                <strong>{leadLabel(item)}</strong>
                <p>{String(item.reason || item.description || item.action || "Evidence review recommended.")}</p>
                {item.confidence_level !== undefined && <StatusChip label={`${String(item.confidence_level)}%`} tone="info" />}
              </article>
            ))}
          </div>
        );
      })}
    </section>
  );
}

