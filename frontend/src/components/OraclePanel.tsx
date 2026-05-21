import { type FormEvent, useMemo, useState } from "react";
import { Bot, BrainCircuit, Filter, Loader2, Radar, Send, Sparkles } from "lucide-react";

type ApiNode = {
  id: string;
  type: string;
  label: string;
  value: string;
  source?: string;
  confidence?: string;
  data?: Record<string, unknown>;
};

type ApiEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  confidence?: string;
  confidence_level?: number;
  data?: Record<string, unknown>;
};

type GraphPayload = { nodes: ApiNode[]; edges: ApiEdge[] };

type OraclePanelProps = {
  token?: string | null;
  investigationId?: string | null;
  graph?: GraphPayload;
  activeNode?: ApiNode | null;
  title?: string;
};

type OracleCommand = {
  type: string;
  nodeType?: string;
  transform?: string;
  reason?: string;
  [key: string]: unknown;
};

type OracleMessage = {
  role: "user" | "oracle" | "system";
  content: string;
  commands?: OracleCommand[];
  provider?: string;
};

const API_BASE = import.meta.env.VITE_API_BASE || "";
const EMPTY_GRAPH: GraphPayload = { nodes: [], edges: [] };

async function apiJson(path: string, options?: RequestInit, token?: string | null) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options?.headers || {}),
    },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) throw new Error(payload.detail || payload.message || `Request failed: ${response.status}`);
  return payload;
}

function graphMetrics(graph: GraphPayload) {
  const byType = graph.nodes.reduce<Record<string, number>>((acc, node) => {
    acc[node.type || "unknown"] = (acc[node.type || "unknown"] || 0) + 1;
    return acc;
  }, {});
  const highConfidence = graph.nodes.filter((node) => ["confirmed", "high"].includes(String(node.confidence || "").toLowerCase())).length;
  const lowConfidence = graph.nodes.filter((node) => ["low", "candidate", "weak"].includes(String(node.confidence || "").toLowerCase())).length;
  return { byType, highConfidence, lowConfidence };
}

function commandLabel(command: OracleCommand): string {
  if (command.type === "highlight_type") return `highlight:${command.nodeType || "entity"}`;
  if (command.type === "clear_highlight") return "clear:highlight";
  if (command.type === "suggest_transform") return `next:${command.transform || "transform"}`;
  return command.type;
}

export default function OraclePanel({ token, investigationId, graph = EMPTY_GRAPH, activeNode = null, title = "AI Oracle" }: OraclePanelProps) {
  const safeGraph = useMemo<GraphPayload>(() => ({ nodes: Array.isArray(graph.nodes) ? graph.nodes : [], edges: Array.isArray(graph.edges) ? graph.edges : [] }), [graph]);
  const metrics = useMemo(() => graphMetrics(safeGraph), [safeGraph]);
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<OracleMessage[]>([
    {
      role: "system",
      content: "Oracle online as an investigation copilot. I can summarize graph posture, recommend next transforms, highlight entity types, and flag weak collection gaps.",
    },
  ]);
  const [loading, setLoading] = useState(false);

  const sendPrompt = async (text: string) => {
    const clean = text.trim();
    if (!clean || loading) return;
    setPrompt("");
    setMessages((previous) => [...previous, { role: "user", content: clean }]);
    setLoading(true);
    try {
      const payload = await apiJson(
        "/api/v1/oracle/chat",
        {
          method: "POST",
          body: JSON.stringify({ prompt: clean, investigation_id: investigationId, graph_state: safeGraph, node: activeNode }),
        },
        token,
      );
      const commands = Array.isArray(payload.data.commands) ? (payload.data.commands as OracleCommand[]) : [];
      commands.forEach((command) => window.dispatchEvent(new CustomEvent("nexus:oracle-command", { detail: command })));
      setMessages((previous) => [
        ...previous,
        {
          role: "oracle",
          content: payload.data.reply || "Oracle returned no narrative.",
          commands,
          provider: payload.data.provider || "unknown",
        },
      ]);
    } catch (error) {
      setMessages((previous) => [
        ...previous,
        {
          role: "oracle",
          content: error instanceof Error ? `Oracle request failed: ${error.message}` : "Oracle request failed.",
          commands: [],
          provider: "client_error",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void sendPrompt(prompt);
  };

  const quickPrompts = [
    "Summarize this investigation and rank the strongest pivots.",
    activeNode ? `Suggest the next OSINT transforms for ${activeNode.type} ${activeNode.label}.` : "Suggest the next OSINT transforms for the current graph.",
    "Show all high-confidence infrastructure and IP pivots.",
    "Find collection gaps and weak-confidence nodes to verify next.",
    "Clear graph highlight.",
  ];

  return (
    <section className="oracle-panel" aria-label="NexusIntel Oracle investigation assistant">
      <header>
        <div>
          <Bot size={16} />
          <strong>{title}</strong>
        </div>
        <span>{safeGraph.nodes.length} nodes / {safeGraph.edges.length} edges</span>
      </header>

      <div className="oracle-metrics" aria-label="Oracle graph metrics">
        <span><Radar size={13} />{metrics.highConfidence} high</span>
        <span><Filter size={13} />{metrics.lowConfidence} weak</span>
        <span><BrainCircuit size={13} />{Object.keys(metrics.byType).length} types</span>
      </div>

      {activeNode && (
        <div className="oracle-context">
          <Sparkles size={14} />
          <span>{activeNode.type.toUpperCase()} / {activeNode.label}</span>
        </div>
      )}

      <div className="oracle-quick-actions">
        {quickPrompts.map((item) => (
          <button key={item} type="button" onClick={() => void sendPrompt(item)} disabled={loading}>
            {item}
          </button>
        ))}
      </div>

      <div className="oracle-messages">
        {messages.map((message, index) => (
          <div className={`oracle-message ${message.role}`} key={`${message.role}:${index}`}>
            <strong>{message.role === "oracle" ? `ORACLE${message.provider ? ` / ${message.provider}` : ""}` : message.role.toUpperCase()}</strong>
            <p>{message.content}</p>
            {!!message.commands?.length && (
              <div className="oracle-command-chips">
                {message.commands.map((command, commandIndex) => <code key={`${command.type}:${commandIndex}`}>{commandLabel(command)}</code>)}
              </div>
            )}
          </div>
        ))}
      </div>

      <form className="oracle-input" onSubmit={submit}>
        <input value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Ask: summarize, highlight IPs, recommend transforms..." />
        <button type="submit" disabled={loading} title="Send to Oracle">
          {loading ? <Loader2 className="spin" size={15} /> : <Send size={15} />}
        </button>
      </form>
    </section>
  );
}
