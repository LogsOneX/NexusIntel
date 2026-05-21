import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";
import { Crosshair, Network, Play, Plus, Trash2 } from "lucide-react";
import { EntityPaletteItem, platformMark } from "./CustomNode";

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

type FlowCanvasProps = {
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

const NODE_STYLE: Record<string, { bg: string; border: string; text: string }> = {
  username: { bg: "#111111", border: "#ffffff", text: "#ffffff" },
  email: { bg: "#111111", border: "#ffffff", text: "#ffffff" },
  domain: { bg: "#111111", border: "#888888", text: "#ffffff" },
  ip: { bg: "#111111", border: "#888888", text: "#ffffff" },
  phone: { bg: "#111111", border: "#888888", text: "#ffffff" },
  profile: { bg: "#0a0a0a", border: "#333333", text: "#ffffff" },
  platform: { bg: "#0a0a0a", border: "#333333", text: "#ffffff" },
  service: { bg: "#0a0a0a", border: "#333333", text: "#ffffff" },
  signal: { bg: "#0a0a0a", border: "#333333", text: "#888888" },
  guardrail: { bg: "#000000", border: "#ffffff", text: "#ffffff" },
  target: { bg: "#111111", border: "#ffffff", text: "#ffffff" },
};

const PALETTE_TYPES = ["username", "email", "domain", "ip", "phone"] as const;

function displayLabel(node: GraphNode): string {
  return `[${platformMark(node.type, node.label, node.value)}] ${node.label || node.value}`;
}

function transformsFor(node: GraphNode): TransformAction[] {
  if (node.type === "username" || node.type === "name" || node.type === "profile_candidate") {
    return [
      { id: "maigret_username", label: "Logic Flow: Public Identity Sweep", description: "Normalize profile candidates and run the legacy NexusRecon engine" },
      { id: "sherlock_username", label: "Logic Flow: Cross Platform Pivot", description: "Check public username surfaces through local wrappers" },
    ];
  }
  if (node.type === "email") {
    return [
      { id: "email_footprint", label: "Logic Flow: Email Footprint", description: "Validate syntax, split local/domain, MX, TXT, DMARC, BIMI" },
      { id: "google_osint", label: "Logic Flow: Workspace Signals", description: "Infer public Google/Microsoft workspace posture without paid APIs" },
      { id: "maigret_username", label: "Logic Flow: Local-Part Pivot", description: "Use the email local part as a username investigation seed" },
    ];
  }
  if (node.type === "domain") {
    return [
      { id: "domain_recon", label: "Logic Flow: Extract DNS", description: "Resolve A, AAAA, MX, NS, TXT, CAA and CNAME records" },
      { id: "network_recon", label: "Logic Flow: RDAP + crt.sh", description: "Pull RDAP metadata and passive certificate subdomains" },
      { id: "workspace_recon", label: "Logic Flow: Mail Surface", description: "Infer mail providers and authentication controls" },
    ];
  }
  if (node.type === "ip") {
    return [
      { id: "ip_recon", label: "Logic Flow: IP Recon", description: "Reverse DNS, RDAP allocation and free GeoIP/ASN hints" },
      { id: "reverse_dns", label: "Logic Flow: Reverse DNS", description: "Create linked hostnames from public PTR records" },
    ];
  }
  if (node.type === "phone") {
    return [
      { id: "phone_recon", label: "Logic Flow: Numbering Plan", description: "Validate E.164 and map public numbering-plan/carrier hints" },
      { id: "numbering_plan", label: "Logic Flow: Line-Type Hint", description: "Create offline public line-type signals" },
    ];
  }
  return [
    { id: "network_recon", label: "Logic Flow: Infrastructure Pivot", description: "Run public DNS/network transforms from this entity value" },
  ];
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

export default function FlowCanvas({
  investigationId,
  nodes,
  edges,
  selectedNode,
  onSelectNode,
  onGraphUpdate,
  onTaskStart,
  onError,
}: FlowCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const pollers = useRef<Record<string, number>>({});
  const seenNodeIds = useRef<Set<string>>(new Set());
  const nodesRef = useRef<Map<string, GraphNode>>(new Map());
  const dashAnimation = useRef<number | null>(null);
  const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null);
  const [runningTask, setRunningTask] = useState<string | null>(null);
  const [runningNodeId, setRunningNodeId] = useState<string | null>(null);
  const [dropHint, setDropHint] = useState(false);

  useEffect(() => {
    nodesRef.current = new Map(nodes.map((node) => [node.id, node]));
  }, [nodes]);

  const elements = useMemo(
    () => [
      ...nodes.map((node) => {
        const style = NODE_STYLE[node.type] || NODE_STYLE.signal;
        return {
          data: {
            id: node.id,
            label: displayLabel(node),
            rawLabel: node.label,
            type: node.type,
            value: node.value,
            confidence: node.confidence || "medium",
            bg: style.bg,
            border: style.border,
            text: style.text,
          },
          classes: `entity ${node.type} ${node.confidence === "low" ? "low-confidence" : ""} ${node.id === runningNodeId ? "processing" : ""}`,
        };
      }),
      ...edges.map((edge) => ({
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          label: edge.type.replaceAll("_", " "),
          confidence: edge.confidence || "medium",
        },
        classes: `edge ${edge.confidence === "low" ? "low-confidence" : ""} ${runningTask ? "running-flow" : ""}`,
      })),
    ],
    [edges, nodes, runningNodeId, runningTask],
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
            setRunningTask(null);
            setRunningNodeId(null);
          }
        } catch (error) {
          window.clearInterval(pollers.current[taskId]);
          delete pollers.current[taskId];
          setRunningTask(null);
          setRunningNodeId(null);
          onError(error instanceof Error ? error.message : "Graph polling failed");
        }
      }, 1800);
    },
    [onError, onGraphUpdate],
  );

  const runTransform = useCallback(
    async (node: GraphNode, transform: string) => {
      if (!investigationId) {
        onError("Create or select an investigation before running transforms.");
        return;
      }
      setContextMenu(null);
      setRunningNodeId(node.id);
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
        setRunningTask(payload.data.task_id);
        onTaskStart(payload.data.task_id, transform, node);
        pollGraphUntilComplete(payload.data.task_id);
      } catch (error) {
        setRunningTask(null);
        setRunningNodeId(null);
        onError(error instanceof Error ? error.message : "Transform failed");
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

  const createDroppedEntity = useCallback(
    async (kind: string) => {
      if (!investigationId) {
        onError("Create or select an investigation before dropping entities.");
        return;
      }
      const value = window.prompt(`Add ${kind} value`);
      if (!value?.trim()) return;
      const payload = await apiJson("/api/v1/entities", {
        method: "POST",
        body: JSON.stringify({
          investigation_id: investigationId,
          type: kind,
          label: value.trim(),
          value: value.trim(),
          source_id: selectedNode?.id || null,
          relationship_type: selectedNode ? "manual_pivot" : "manual_seed",
          data: { created_from: "drag_drop_pipeline", parent: selectedNode?.id || null },
        }),
      });
      onGraphUpdate(payload.data.graph);
    },
    [investigationId, onError, onGraphUpdate, selectedNode?.id],
  );

  useEffect(() => {
    if (!containerRef.current || cyRef.current) return;
    cyRef.current = cytoscape({
      container: containerRef.current,
      wheelSensitivity: 0.08,
      minZoom: 0.2,
      maxZoom: 2.8,
      style: [
        {
          selector: "node",
          style: {
            width: 128,
            height: 52,
            shape: "round-rectangle",
            "background-color": "data(bg)",
            "background-opacity": 1,
            "border-width": 1,
            "border-color": "data(border)",
            color: "data(text)",
            label: "data(label)",
            "font-family": "JetBrains Mono, ui-monospace, monospace",
            "font-size": 9,
            "font-weight": 600,
            "text-wrap": "wrap",
            "text-max-width": 112,
            "text-valign": "center",
            "text-halign": "center",
            "overlay-opacity": 0,
            "transition-property": "opacity border-width background-color border-color",
            "transition-duration": "240ms",
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 2,
            "border-color": "#ffffff",
            "background-color": "#111111",
          },
        },
        {
          selector: "node.processing",
          style: {
            "border-width": 2,
            "border-color": "#ffffff",
            "shadow-blur": 12,
            "shadow-color": "#ffffff",
            "shadow-opacity": 0.28,
            "shadow-offset-x": 0,
            "shadow-offset-y": 0,
          },
        },
        {
          selector: "node.low-confidence",
          style: {
            "border-style": "dashed",
            "border-color": "#888888",
            color: "#888888",
          },
        },
        {
          selector: "edge",
          style: {
            width: 1,
            "line-color": "#333333",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#333333",
            "curve-style": "bezier",
            "line-style": "solid",
            label: "data(label)",
            color: "#888888",
            "font-family": "JetBrains Mono, ui-monospace, monospace",
            "font-size": 7,
            "text-background-color": "#000000",
            "text-background-opacity": 0.86,
            "text-background-padding": 2,
            "overlay-opacity": 0,
          },
        },
        {
          selector: "edge.running-flow",
          style: {
            "line-style": "dashed",
            "line-dash-pattern": [8, 6],
            "line-color": "#ffffff",
            "target-arrow-color": "#ffffff",
          },
        },
        {
          selector: "edge.low-confidence",
          style: {
            "line-style": "dashed",
            "line-color": "#888888",
            "target-arrow-color": "#888888",
          },
        },
      ],
      layout: { name: "cose", animate: false, fit: true, padding: 88 },
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
      onSelectNode(nodesRef.current.get(nodeId) || null);
      setContextMenu(null);
    });
    cy.on("cxttap", "node", (event) => {
      const nodeId = event.target.id();
      const node = nodesRef.current.get(nodeId);
      if (!node || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const position = event.renderedPosition || { x: rect.width / 2, y: rect.height / 2 };
      onSelectNode(node);
      setContextMenu({ x: rect.left + position.x, y: rect.top + position.y, node });
    });

    return () => {
      Object.values(pollers.current).forEach((id) => window.clearInterval(id));
      pollers.current = {};
      if (dashAnimation.current) cancelAnimationFrame(dashAnimation.current);
      cy.destroy();
      cyRef.current = null;
    };
  }, [onSelectNode]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    const previous = seenNodeIds.current;
    const incomingIds = new Set(nodes.map((node) => node.id));
    const freshIds = nodes.filter((node) => !previous.has(node.id)).map((node) => node.id);
    seenNodeIds.current = incomingIds;

    cy.elements().remove();
    cy.add(elements as cytoscape.ElementDefinition[]);
    const layoutName = nodes.length > 34 ? "breadthfirst" : "cose";
    cy.layout({
      name: layoutName,
      animate: true,
      animationDuration: 520,
      animationEasing: "ease-out-cubic",
      fit: true,
      padding: 96,
    }).run();

    freshIds.forEach((id) => {
      const node = cy.getElementById(id);
      const position = node.position();
      node.style("opacity", 0);
      node.position({ x: position.x - 14, y: position.y - 6 });
      node.animate({ style: { opacity: 1 }, position }, { duration: 380, easing: "ease-out-cubic" });
    });
  }, [elements, nodes]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().unselect();
    if (selectedNode) cy.getElementById(selectedNode.id).select();
  }, [selectedNode]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || typeof ResizeObserver === "undefined") return undefined;
    let frame = 0;
    const observer = new ResizeObserver(() => {
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const cy = cyRef.current;
        if (!cy) return;
        cy.resize();
        cy.fit(undefined, 96);
      });
    });
    observer.observe(container);
    return () => {
      if (frame) cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, []);


  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    let offset = 0;
    const tick = () => {
      if (runningTask) {
        offset = (offset + 1) % 28;
        cy.edges(".running-flow").style("line-dash-offset", offset);
        dashAnimation.current = requestAnimationFrame(tick);
      }
    };
    if (runningTask) dashAnimation.current = requestAnimationFrame(tick);
    return () => {
      if (dashAnimation.current) cancelAnimationFrame(dashAnimation.current);
      dashAnimation.current = null;
    };
  }, [runningTask]);

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
    <section className={dropHint ? "tactical-graph-shell drop-active" : "tactical-graph-shell"}>
      <header className="tactical-graph-toolbar">
        <div>
          <span className="micro-label">Visual Link Analysis</span>
          <strong>{nodes.length} ENTITIES</strong>
          <span>{edges.length} RELATIONSHIPS</span>
        </div>
        <div className="entity-pipeline" aria-label="Drag entities to the graph">
          {PALETTE_TYPES.map((kind) => (
            <EntityPaletteItem kind={kind} key={kind} />
          ))}
        </div>
        <div className="tactical-graph-actions">
          <button className="icon-button" type="button" onClick={() => cyRef.current?.fit(undefined, 96)} title="Fit graph">
            <Crosshair size={16} />
          </button>
          <button
            className="icon-button"
            type="button"
            onClick={() => cyRef.current?.layout({ name: "cose", animate: true, animationDuration: 520, fit: true, padding: 96 }).run()}
            title="Re-layout"
          >
            <Network size={16} />
          </button>
        </div>
      </header>

      <div
        className="tactical-graph-canvas"
        ref={containerRef}
        onDragOver={(event) => {
          event.preventDefault();
          setDropHint(true);
        }}
        onDragLeave={() => setDropHint(false)}
        onDrop={(event) => {
          event.preventDefault();
          setDropHint(false);
          const kind = event.dataTransfer.getData("application/x-nexus-entity");
          if (kind) createDroppedEntity(kind).catch((error) => onError(error instanceof Error ? error.message : "Failed to add dropped entity"));
        }}
      >
        {!nodes.length && (
          <div className="empty-graph">
            <Plus size={22} />
            <strong>NO GRAPH LOADED</strong>
            <span>Launch a target or drag an entity to begin the intelligence pipeline.</span>
          </div>
        )}
      </div>

      {contextMenu && (
        <div
          className="graph-context-menu"
          style={{ transform: `translate3d(${Math.min(contextMenu.x, window.innerWidth - 340)}px, ${Math.min(contextMenu.y, window.innerHeight - 390)}px, 0)` }}
          onClick={(event) => event.stopPropagation()}
        >
          <div className="context-node-card">
            <div className="context-node-mark">{platformMark(contextMenu.node.type, contextMenu.node.label, contextMenu.node.value)}</div>
            <div>
              <strong>{contextMenu.node.label}</strong>
              <span>{contextMenu.node.type.toUpperCase()} / {(contextMenu.node.confidence || "medium").toUpperCase()}</span>
            </div>
          </div>
          <div className="context-actions">
            {transformsFor(contextMenu.node).map((action) => (
              <button key={action.id} type="button" disabled={Boolean(runningTask)} onClick={() => runTransform(contextMenu.node, action.id)}>
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
                <strong>REMOVE ENTITY</strong>
                <small>Delete node and attached relationships</small>
              </span>
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
