import { CalendarClock, GitBranch, Radio } from "lucide-react";
import type { GraphEdge, GraphNode } from "./GraphCanvas";

type TimelineViewProps = {
  nodes: GraphNode[];
  edges: GraphEdge[];
  onSelectNode?: (node: GraphNode) => void;
};

type TimelineEntry = {
  id: string;
  timestamp: string;
  title: string;
  kind: string;
  source: string;
  detail: string;
  node: GraphNode;
};

function asString(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value.trim();
  return null;
}

function firstTimestamp(node: GraphNode): string {
  const props = node.nodeProperties || {};
  const direct =
    asString(props.created_at) ||
    asString(props.createdAt) ||
    asString(props.updated_at) ||
    asString(props.timestamp) ||
    asString(props.first_seen) ||
    asString(props.last_seen);
  if (direct) return direct;

  const rdap = props.rdap as { events?: Array<{ eventDate?: string; eventAction?: string }> } | undefined;
  const event = rdap?.events?.find((item) => item.eventDate);
  if (event?.eventDate) return event.eventDate;

  const nestedEvents = props.events as Array<{ timestamp?: string; date?: string; created_at?: string }> | undefined;
  const nested = nestedEvents?.find((item) => item.timestamp || item.date || item.created_at);
  return nested?.timestamp || nested?.date || nested?.created_at || new Date().toISOString();
}

function entryDetail(node: GraphNode, connected: number): string {
  const props = node.nodeProperties || {};
  const source = asString(props.source) || asString((props.artifact as Record<string, unknown> | undefined)?.source) || "graph";
  const confidence = asString(props.confidence) || asString((props.artifact as Record<string, unknown> | undefined)?.confidence) || "medium";
  return `${source.toUpperCase()} / ${confidence.toUpperCase()} / ${connected} LINK${connected === 1 ? "" : "S"}`;
}

export default function TimelineView({ nodes, edges, onSelectNode }: TimelineViewProps) {
  const entries: TimelineEntry[] = nodes
    .map((node) => {
      const connected = edges.filter((edge) => edge.source === node.id || edge.target === node.id).length;
      return {
        id: node.id,
        timestamp: firstTimestamp(node),
        title: node.nodeLabel,
        kind: node.nodeType,
        source: node.nodeIcon || node.nodeType.slice(0, 3).toUpperCase(),
        detail: entryDetail(node, connected),
        node,
      };
    })
    .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());

  return (
    <section className="timeline-view" aria-label="Temporal analysis timeline">
      <header className="timeline-header">
        <div>
          <span className="micro-label">Temporal Analysis</span>
          <strong>{entries.length} timestamped intelligence events</strong>
        </div>
        <CalendarClock size={18} />
      </header>

      <div className="timeline-list">
        {entries.map((entry) => (
          <button className="timeline-entry" key={entry.id} type="button" onClick={() => onSelectNode?.(entry.node)}>
            <span className="timeline-dot"><Radio size={12} /></span>
            <span className="timeline-time">{new Date(entry.timestamp).toLocaleString()}</span>
            <span className="timeline-body">
              <strong>{entry.title}</strong>
              <code>{entry.kind.toUpperCase()} / {entry.source}</code>
              <small>{entry.detail}</small>
            </span>
            <GitBranch size={14} />
          </button>
        ))}
        {!entries.length && (
          <div className="timeline-empty">
            <CalendarClock size={20} />
            <strong>No temporal events</strong>
            <span>Run a transform or add an entity to populate the intelligence timeline.</span>
          </div>
        )}
      </div>
    </section>
  );
}
