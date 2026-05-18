import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";
import { Crosshair, Database, Globe, Mail, Network, Play, Plus, Trash2, UserRound } from "lucide-react";

type GraphNode = {
  id: string;
  type: string;
  label: string;
  value: string;
  source?: string;
  confidence?: string;
  data?: Record<string, unknown>;
};

type GraphEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  confidence?: string;
  data?: Record<string, unknown>;
};

type GraphPayload = {
  nodes: GraphNode[];
  edges: GraphEdge[];
};

type TransformAction = {
  id: string;
  label: string;
  description: string;
};

type ContextMenu = {
  x: number;
  y: number;
  node: GraphNode;
};

type GraphCanvasProps = {
  investigationId: string | null;
  nodes: GraphNode[];
  edges: GraphEdge[];
  selectedNode: GraphNode | null;
  onSelectNode: (node: GraphNode | null) => void;
  onGraphUpdate: (graph: GraphPayload) => void;
  onTaskStart: (taskId: string, transform: string, node: GraphNode) => void;
  onError: (message: string) => void;
};

const API_BASE = import.meta.env.VITE_API_BASE || "";

const NODE_COLORS: Record<string, string> = {
  username: "#38bdf8",
  email: "#22c55e",
  domain: "#f59e0b",
  ip: "#f97316",
  profile: "#a78bfa",
  platform: "#e2e8f0",
  service: "#14b8a6",
  dns_record: "#64748b",
  avatar_hash: "#fb7185",
  phone: "#facc15",
  target: "#38bdf8",
};

function platformMark(node: GraphNode): string {
  const raw = String(node.data?.icon || node.label || node.value || "").toLowerCase();
  if (raw.includes("github")) return "GH";
  if (raw.includes("gitlab")) return "GL";
  if (raw.includes("google") || raw.includes("gmail")) return "G";
  if (raw.includes("microsoft") || raw.includes("outlook")) return "MS";
  if (raw.includes("instagram")) return "IG";
  if (raw.includes("linkedin")) return "IN";
  if (raw.includes("reddit")) return "RD";
  if (raw.includes("tiktok")) return "TT";
  if (raw === "x" || raw.includes("twitter")) return "X";
  if (node.type === "email") return "@";
  if (node.type === "domain") return "DNS";
  if (node.type === "ip") return "IP";
  if (node.type === "username") return "ID";
  return node.type.slice(0, 2).toUpperCase();
}

function displayLabel(node: GraphNode): string {
  return `[${platformMark(node)}] ${node.label || node.value}`;
}

function transformsFor(node: GraphNode): TransformAction[] {
  if (node.type === "username") {
    return [
      { id: "maigret_username", label: "Username sweep", description: "Mass public profile enumeration" },
      { id: "sherlock_username", label: "Sherlock-style pivot", description: "Cross-platform existence checks" },
      { id: "email_footprint", label: "Derive email pivots", description: "Extract domain and local-part signals when present" },
    ];
  }
  if (node.type === "email") {
    return [
      { id: "email_footprint", label: "Email footprint", description: "MX, TXT, DMARC, BIMI and public avatar signals" },
      { id: "google_osint", label: "Google workspace map", description: "Public Google Workspace indicators without paid APIs" },
      { id: "maigret_username", label: "Username from local part", description: "Pivot the email local part across public platforms" },
    ];
  }
  if (node.type === "domain") {
    return [
      { id: "domain_recon", label: "Domain recon", description: "DNS, mail, service and candidate subdomain mapping" },
      { id: "workspace_recon", label: "Workspace recon", description: "Email infrastructure and provider inference" },
      { id: "website_recon", label: "Website surface", description: "Resolve web-facing infrastructure signals" },
    ];
  }
  if (node.type === "profile" || node.type === "platform") {
    return [
      { id: "domain_recon", label: "Resolve host", description: "Map profile host and DNS edges" },
      { id: "maigret_username", label: "Re-run identity sweep", description: "Use this profile as a pivot source" },
    ];
  }
  return [
    { id: "domain_recon", label: "Infrastructure pivot", description: "Map DNS and network records" },
    { id: "email_footprint", label: "Identity pivot", description: "Inspect public email/workspace signals" },
  ];
}

function iconForNode(type: string) {
  if (type === "username") return <UserRound size={15} />;
  if (type === "email") return <Mail size={15} />;
  if (type === "domain") return <Globe size={15} />;
  if (type === "ip") return <Network size={15} />;
  if (type === "service" || type === "platform") return <Database size={15} />;
  return <Crosshair size={15} />;
}

async function apiJson(path: string, options?: RequestInit) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
    ...options,
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok || payload.ok === false) {
    throw new Error(payload.detail || payload.message || `Request failed: ${response.status}`);
  }
  return payload;
}

export default function GraphCanvas({
  investigationId,
  nodes,
  edges,
  selectedNode,
  onSelectNode,
  onGraphUpdate,
  onTaskStart,
  onError,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const pollers = useRef<Record<string, number>>({});
  const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null);
  const [runningTransform, setRunningTransform] = useState<string | null>(null);

  const elements = useMemo(
    () => [
      ...nodes.map((node) => ({
        data: {
          id: node.id,
          label: displayLabel(node),
          rawLabel: node.label,
          type: node.type,
          value: node.value,
          confidence: node.confidence || "medium",
          color: NODE_COLORS[node.type] || "#94a3b8",
        },
        classes: `entity ${node.type}`,
      })),
      ...edges.map((edge) => ({
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.type.replaceAll("_", " "),
          confidence: edge.confidence || "medium",
        },
        classes: edge.confidence === "low" ? "low-confidence" : "edge",
      })),
    ],
    [nodes, edges],
  );

  const pollGraphUntilComplete = useCallback(
    (taskId: string) => {
      if (pollers.current[taskId]) window.clearInterval(pollers.current[taskId]);
      pollers.current[taskId] = window.setInterval(async () => {
        try {
          const graphPayload = await apiJson(`/api/v1/tasks/${taskId}/graph`);
          onGraphUpdate(graphPayload.data);
          const taskPayload = await apiJson(`/api/v1/tasks/${taskId}`);
          if (["completed", "failed"].includes(taskPayload.data.status)) {
            window.clearInterval(pollers.current[taskId]);
            delete pollers.current[taskId];
          }
        } catch (error) {
          window.clearInterval(pollers.current[taskId]);
          delete pollers.current[taskId];
          onError(error instanceof Error ? error.message : "Graph polling failed");
        }
      }, 2200);
    },
    [onError, onGraphUpdate],
  );

  const runTransform = useCallback(
    async (node: GraphNode, transform: string) => {
      if (!investigationId) {
        onError("Create or select an investigation before running transforms.");
        return;
      }
      setRunningTransform(transform);
      setContextMenu(null);
      try {
        const payload = await apiJson("/api/v1/transforms", {
          method: "POST",
          body: JSON.stringify({
            investigation_id: investigationId,
            node_id: node.id,
            transform,
            mode: "standard",
          }),
        });
        onTaskStart(payload.data.task_id, transform, node);
        pollGraphUntilComplete(payload.data.task_id);
      } catch (error) {
        onError(error instanceof Error ? error.message : "Transform failed");
      } finally {
        setRunningTransform(null);
      }
    },
    [investigationId, onError, onTaskStart, pollGraphUntilComplete],
  );

  const deleteNode = useCallback(
    async (node: GraphNode) => {
      if (!investigationId) return;
      setContextMenu(null);
      try {
        const payload = await apiJson(`/api/v1/investigations/${investigationId}/entities/${node.id}`, { method: "DELETE" });
        onGraphUpdate(payload.data.graph);
        if (selectedNode?.id === node.id) onSelectNode(null);
      } catch (error) {
        onError(error instanceof Error ? error.message : "Delete failed");
      }
    },
    [investigationId, onError, onGraphUpdate, onSelectNode, selectedNode?.id],
  );

  useEffect(() => {
    if (!containerRef.current || cyRef.current) return;
    cyRef.current = cytoscape({
      container: containerRef.current,
      wheelSensitivity: 0.18,
      minZoom: 0.25,
      maxZoom: 2.5,
      style: [
        {
          selector: "node",
          style: {
            width: 74,
            height: 74,
            "background-color": "data(color)",
            "background-opacity": 0.16,
            "border-width": 2,
            "border-color": "data(color)",
            color: "#e5edf5",
            label: "data(label)",
            "font-family": "Inter, system-ui, sans-serif",
            "font-size": 10,
            "text-wrap": "wrap",
            "text-max-width": 118,
            "text-valign": "bottom",
            "text-halign": "center",
            "text-margin-y": 8,
            "overlay-opacity": 0,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 4,
            "border-color": "#ffffff",
            "background-opacity": 0.32,
            "shadow-blur": 20,
            "shadow-color": "#38bdf8",
            "shadow-opacity": 0.75,
          },
        },
        {
          selector: "edge",
          style: {
            width: 1.6,
            "line-color": "#334155",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#475569",
            "curve-style": "bezier",
            label: "data(label)",
            color: "#94a3b8",
            "font-size": 8,
            "text-background-color": "#050b12",
            "text-background-opacity": 0.82,
            "text-background-padding": 2,
          },
        },
        {
          selector: ".low-confidence",
          style: {
            "line-style": "dashed",
            "line-color": "#64748b",
            "target-arrow-color": "#64748b",
          },
        },
      ],
      layout: { name: "cose", animate: false, fit: true, padding: 80 },
    });

    const cy = cyRef.current;
    cy.on("tap", (event) => {
      if (event.target === cy) {
        setContextMenu(null);
        onSelectNode(null);
      }
    });
    cy.on("tap", "node", (event) => {
      const nodeId = event.target.id();
      onSelectNode(nodes.find((item) => item.id === nodeId) || null);
      setContextMenu(null);
    });
    cy.on("cxttap", "node", (event) => {
      const nodeId = event.target.id();
      const node = nodes.find((item) => item.id === nodeId);
      if (!node || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const position = event.renderedPosition || { x: rect.width / 2, y: rect.height / 2 };
      onSelectNode(node);
      setContextMenu({ x: rect.left + position.x, y: rect.top + position.y, node });
    });

    return () => {
      Object.values(pollers.current).forEach((id) => window.clearInterval(id));
      pollers.current = {};
      cy.destroy();
      cyRef.current = null;
    };
  }, [nodes, onSelectNode]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().remove();
    cy.add(elements as cytoscape.ElementDefinition[]);
    const layoutName = nodes.length > 30 ? "breadthfirst" : "cose";
    cy.layout({ name: layoutName, animate: true, animationDuration: 480, fit: true, padding: 90 }).run();
  }, [elements, nodes.length]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().unselect();
    if (selectedNode) cy.getElementById(selectedNode.id).select();
  }, [selectedNode]);

  useEffect(() => {
    const close = () => setContextMenu(null);
    window.addEventListener("click", close);
    window.addEventListener("resize", close);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("resize", close);
    };
  }, []);

  return (
    <section className="tactical-graph-shell">
      <header className="tactical-graph-toolbar">
        <div>
          <span className="micro-label">Visual Link Analysis</span>
          <strong>{nodes.length} entities</strong>
          <span>{edges.length} relationships</span>
        </div>
        <div className="tactical-graph-actions">
          <button className="icon-button" type="button" onClick={() => cyRef.current?.fit(undefined, 90)} title="Fit graph">
            <Crosshair size={16} />
          </button>
          <button className="icon-button" type="button" onClick={() => cyRef.current?.layout({ name: "cose", animate: true, fit: true, padding: 90 }).run()} title="Re-layout">
            <Network size={16} />
          </button>
        </div>
      </header>

      <div className="tactical-graph-canvas" ref={containerRef}>
        {!nodes.length && (
          <div className="empty-graph">
            <Plus size={22} />
            <strong>No investigation graph loaded</strong>
            <span>Create a target from the left console to start building entities.</span>
          </div>
        )}
      </div>

      {contextMenu && (
        <div
          className="graph-context-menu"
          style={{ left: Math.min(contextMenu.x, window.innerWidth - 310), top: Math.min(contextMenu.y, window.innerHeight - 360) }}
          onClick={(event) => event.stopPropagation()}
        >
          <div className="context-node-card">
            {iconForNode(contextMenu.node.type)}
            <div>
              <strong>{contextMenu.node.label}</strong>
              <span>{contextMenu.node.type} / {contextMenu.node.confidence || "medium"}</span>
            </div>
          </div>
          <div className="context-actions">
            {transformsFor(contextMenu.node).map((action) => (
              <button
                key={action.id}
                type="button"
                disabled={Boolean(runningTransform)}
                onClick={() => runTransform(contextMenu.node, action.id)}
              >
                <Play size={14} />
                <span>
                  <strong>{action.label}</strong>
                  <small>{action.description}</small>
                </span>
              </button>
            ))}
            <button className="context-danger" type="button" onClick={() => deleteNode(contextMenu.node)}>
              <Trash2 size={14} />
              <span>
                <strong>Remove entity</strong>
                <small>Delete this node and attached relationships</small>
              </span>
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
