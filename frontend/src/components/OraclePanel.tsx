import { FormEvent, useState } from "react";
import { Bot, Send, Sparkles } from "lucide-react";

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

type OracleMessage = {
  role: "user" | "oracle" | "system";
  content: string;
};

const API_BASE = import.meta.env.VITE_API_BASE || "";

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

export default function OraclePanel({ token, investigationId, graph = { nodes: [], edges: [] }, activeNode = null, title = "AI Oracle" }: OraclePanelProps) {
  const [prompt, setPrompt] = useState("");
  const [messages, setMessages] = useState<OracleMessage[]>([
    { role: "system", content: "Oracle online. Ask for graph filters, node pivots, executive summaries, or next transforms." },
  ]);
  const [loading, setLoading] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const text = prompt.trim();
    if (!text) return;
    setPrompt("");
    setMessages((previous) => [...previous, { role: "user", content: text }]);
    setLoading(true);
    try {
      const payload = await apiJson(
        "/api/v1/oracle/chat",
        {
          method: "POST",
          body: JSON.stringify({ prompt: text, investigation_id: investigationId, graph_state: graph, node: activeNode }),
        },
        token,
      );
      const reply = payload.data.reply || "Oracle returned no narrative.";
      const commands = payload.data.commands || [];
      commands.forEach((command: Record<string, unknown>) => window.dispatchEvent(new CustomEvent("nexus:oracle-command", { detail: command })));
      setMessages((previous) => [...previous, { role: "oracle", content: reply }]);
    } catch (error) {
      setMessages((previous) => [...previous, { role: "oracle", content: error instanceof Error ? error.message : "Oracle request failed" }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="oracle-panel">
      <header>
        <div>
          <Bot size={16} />
          <strong>{title}</strong>
        </div>
        <span>{graph.nodes.length} nodes / {graph.edges.length} edges</span>
      </header>
      {activeNode && (
        <div className="oracle-context">
          <Sparkles size={14} />
          <span>{activeNode.type.toUpperCase()} / {activeNode.label}</span>
        </div>
      )}
      <div className="oracle-messages">
        {messages.map((message, index) => (
          <div className={`oracle-message ${message.role}`} key={`${message.role}:${index}`}>
            <strong>{message.role === "oracle" ? "ORACLE" : message.role.toUpperCase()}</strong>
            <p>{message.content}</p>
          </div>
        ))}
      </div>
      <form className="oracle-input" onSubmit={submit}>
        <input value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="Ask: highlight high-confidence IPs, summarize this graph..." />
        <button type="submit" disabled={loading} title="Send to Oracle">
          <Send size={15} />
        </button>
      </form>
    </section>
  );
}
