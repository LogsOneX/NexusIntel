import { type Dispatch, type FormEvent, type SetStateAction, useCallback, useEffect, useMemo, useRef, useState } from "react";
import cytoscape from "cytoscape";
import { Clock3, Crosshair, Download, GitBranch, Network, PanelBottom, PanelRight, Play, Plus, Radio, RotateCcw, Search, Trash2, Undo2 } from "lucide-react";
import { EntityPaletteItem, platformMark } from "./CustomNode";
import TimelineView from "./TimelineView";

export type GraphNode = {
  id: string;
  nodeType: string;
  nodeLabel: string;
  nodeProperties: Record<string, unknown>;
  nodeShape: "circle" | "square" | "hexagon" | "triangle";
  x: number;
  y: number;
  nodeIcon: string | null;
  nodeFlag: string | null;
};

export type GraphEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
  confidence_level?: number;
};

type ApiGraphNode = {
  id: string;
  type: string;
  label: string;
  value: string;
  source?: string;
  confidence?: string;
  confidence_level?: number;
  data?: Record<string, unknown>;
  created_at?: string;
};

type ApiGraphEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  confidence?: string;
  confidence_level?: number;
  data?: Record<string, unknown>;
  created_at?: string;
};

type ApiGraphPayload = {
  nodes: ApiGraphNode[];
  edges: ApiGraphEdge[];
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

type LayoutMode = "tree" | "circular" | "force";
type ContextTab = "transforms" | "playbooks";

type GraphCanvasProps = {
  investigationId: string | null;
  nodes: ApiGraphNode[];
  edges: ApiGraphEdge[];
  selectedNode: ApiGraphNode | null;
  onSelectNode: (node: ApiGraphNode | null) => void;
  onGraphUpdate: (graph: ApiGraphPayload) => void;
  onTaskStart: (taskId: string, transform: string, node: ApiGraphNode) => void;
  onError: (message: string) => void;
  onSystemLog?: (message: string) => void;
  onOracleNode?: (node: ApiGraphNode) => void;
  searchTarget: string;
  setSearchTarget: Dispatch<SetStateAction<string>>;
  reconMode: "passive" | "standard" | "aggressive";
  setReconMode: Dispatch<SetStateAction<"passive" | "standard" | "aggressive">>;
  onLaunch: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
  isLaunching: boolean;
  terminalOpen: boolean;
  setTerminalOpen: Dispatch<SetStateAction<boolean>>;
  dataPanelOpen: boolean;
  setDataPanelOpen: Dispatch<SetStateAction<boolean>>;
};

const API_BASE = import.meta.env.VITE_API_BASE || "";
const PALETTE_TYPES = ["username", "email", "domain", "ip", "phone"] as const;
const HISTORY_LIMIT = 40;
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

function upperSnake(value: string): string {
  const normalized = value.replace(/([a-z0-9])([A-Z])/g, "$1_$2").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  return (normalized || "RELATED_TO").toUpperCase();
}

function confidenceScore(value?: string): number | undefined {
  const raw = String(value || "").toLowerCase();
  if (["confirmed", "high", "success", "true"].includes(raw)) return 90;
  if (["medium", "observed", "probable"].includes(raw)) return 60;
  if (["low", "weak", "candidate", "false"].includes(raw)) return 30;
  return undefined;
}

function shapeFor(type: string): GraphNode["nodeShape"] {
  if (["domain", "platform", "service", "dns_record"].includes(type)) return "hexagon";
  if (["ip", "profile", "avatar_hash", "signal"].includes(type)) return "square";
  if (["phone", "guardrail", "breach", "risk"].includes(type)) return "triangle";
  return "circle";
}

function cyShape(shape: GraphNode["nodeShape"]): string {
  if (shape === "circle") return "ellipse";
  if (shape === "square") return "rectangle";
  if (shape === "triangle") return "triangle";
  return "hexagon";
}

function labelForApiNode(node: ApiGraphNode): string {
  return node.label || node.value || node.type;
}

function iconForApiNode(node: ApiGraphNode): string | null {
  return platformMark(node.type, node.label, node.value);
}

function apiNodeFromStrict(node: GraphNode): ApiGraphNode {
  return {
    id: node.id,
    type: node.nodeType,
    label: node.nodeLabel,
    value: String(node.nodeProperties.value || node.nodeLabel),
    source: String(node.nodeProperties.source || "graph"),
    confidence: String(node.nodeProperties.confidence || "medium"),
    data: node.nodeProperties,
    created_at: String(node.nodeProperties.created_at || new Date().toISOString()),
  };
}

function strictNodeFromApi(
  node: ApiGraphNode,
  previous: GraphNode | undefined,
  index: number,
  parentPosition?: { x: number; y: number; siblingIndex: number },
): GraphNode {
  if (previous) {
    return {
      ...previous,
      nodeType: node.type,
      nodeLabel: labelForApiNode(node),
      nodeProperties: {
        ...(previous.nodeProperties || {}),
        ...(node.data || {}),
        value: node.value,
        source: node.source || "graph",
        confidence: node.confidence || "medium",
        created_at: node.created_at || previous.nodeProperties.created_at || new Date().toISOString(),
      },
      nodeIcon: iconForApiNode(node),
      nodeFlag: node.confidence === "low" ? "LOW" : null,
    };
  }

  const dataX = Number((node.data || {}).x);
  const dataY = Number((node.data || {}).y);
  let x = Number.isFinite(dataX) ? dataX : 180 + (index % 8) * 138;
  let y = Number.isFinite(dataY) ? dataY : 180 + Math.floor(index / 8) * 112;
  if (parentPosition) {
    const radius = 160 + (parentPosition.siblingIndex % 4) * 34;
    const angle = parentPosition.siblingIndex * GOLDEN_ANGLE;
    x = parentPosition.x + Math.cos(angle) * radius;
    y = parentPosition.y + Math.sin(angle) * radius;
  }

  return {
    id: node.id,
    nodeType: node.type,
    nodeLabel: labelForApiNode(node),
    nodeProperties: {
      ...(node.data || {}),
      value: node.value,
      source: node.source || "graph",
      confidence: node.confidence || "medium",
      created_at: node.created_at || new Date().toISOString(),
    },
    nodeShape: shapeFor(node.type),
    x,
    y,
    nodeIcon: iconForApiNode(node),
    nodeFlag: node.confidence === "low" ? "LOW" : null,
  };
}

function strictEdgeFromApi(edge: ApiGraphEdge): GraphEdge {
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: upperSnake(edge.type),
    confidence_level: typeof edge.confidence_level === "number" ? edge.confidence_level : typeof edge.data?.confidence_level === "number" ? edge.data.confidence_level : confidenceScore(edge.confidence),
  };
}

function normalizeGraphPayload(payload: unknown): ApiGraphPayload {
  const raw = (payload || {}) as Partial<ApiGraphPayload>;
  return {
    nodes: Array.isArray(raw.nodes) ? raw.nodes : [],
    edges: Array.isArray(raw.edges) ? raw.edges : [],
  };
}

function cloneState(nodes: GraphNode[], edges: GraphEdge[]) {
  return {
    nodes: JSON.parse(JSON.stringify(nodes)) as GraphNode[],
    edges: JSON.parse(JSON.stringify(edges)) as GraphEdge[],
  };
}

function transformsFor(node: GraphNode): TransformAction[] {
  if (["username", "name", "profile_candidate"].includes(node.nodeType)) {
    return [
      { id: "maigret_username", label: "Username Sweep", description: "Standalone public profile enumeration" },
      { id: "sherlock_username", label: "Sherlock-Style Pivot", description: "Cross-platform existence checks" },
      { id: "email_footprint", label: "Local-Part Email Logic", description: "Derive email/domain pivots when present" },
    ];
  }
  if (node.nodeType === "email") {
    return [
      { id: "email_footprint", label: "Email Footprint", description: "Syntax, MX, TXT, DMARC, BIMI and avatar signals" },
      { id: "google_osint", label: "Workspace Signals", description: "Public Google/Microsoft workspace inference" },
      { id: "maigret_username", label: "Local-Part Username", description: "Pivot the mailbox local-part across public platforms" },
    ];
  }
  if (node.nodeType === "domain") {
    return [
      { id: "domain_recon", label: "Extract DNS", description: "A, AAAA, MX, NS, TXT, CAA and candidate subdomains" },
      { id: "network_recon", label: "RDAP + Certificate Pivots", description: "Public RDAP and passive certificate signals" },
      { id: "workspace_recon", label: "Mail Surface", description: "Infer mail providers and authentication controls" },
    ];
  }
  if (node.nodeType === "ip") {
    return [
      { id: "ip_recon", label: "IP Recon", description: "Reverse DNS, RDAP allocation and public network hints" },
      { id: "reverse_dns", label: "Reverse DNS", description: "Create linked hostname entities from PTR signals" },
    ];
  }
  if (node.nodeType === "phone") {
    return [
      { id: "phone_recon", label: "Numbering Plan", description: "Validate E.164 and map public numbering-plan hints" },
      { id: "carrier_lookup", label: "Carrier Hint", description: "Create public line-type and region signals" },
    ];
  }
  return [{ id: "network_recon", label: "Infrastructure Pivot", description: "Run public DNS/network transforms from this entity" }];
}

function playbooksFor(node: GraphNode): TransformAction[] {
  return [
    {
      id: "full_identity_pipeline",
      label: "Full Identity Machine",
      description: "Email or handle to profiles, domain, MX, DNS, IP and workspace nodes",
    },
    ...(node.nodeType === "email"
      ? [{ id: "email_macro", label: "Email Attack Surface Map", description: "Mailbox to domain, DNS, MX and workspace posture" }]
      : []),
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

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function reportHtml(nodes: GraphNode[], edges: GraphEdge[], imageData: string, investigationId: string | null): string {
  const generatedAt = new Date().toISOString();
  const rows = nodes
    .map(
      (node) => `<tr><td>${escapeHtml(node.nodeType)}</td><td>${escapeHtml(node.nodeLabel)}</td><td>${escapeHtml(node.nodeProperties.value)}</td><td>${escapeHtml(node.nodeProperties.confidence || "medium")}</td></tr>`,
    )
    .join("");
  const edgeRows = edges.map((edge) => `<tr><td>${escapeHtml(edge.source)}</td><td>${escapeHtml(edge.label)}</td><td>${escapeHtml(edge.target)}</td><td>${escapeHtml(edge.confidence_level || "")}</td></tr>`).join("");
  const graphJson = escapeHtml(JSON.stringify({ nodes, edges }, null, 2));
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>NexusIntel Intelligence Report</title>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; background: #000; color: #fff; font-family: Inter, Arial, sans-serif; }
  main { max-width: 1160px; margin: 0 auto; padding: 32px; }
  h1, h2 { margin: 0; text-transform: uppercase; letter-spacing: 0; }
  header { border: 1px solid #333; padding: 18px; margin-bottom: 18px; background: #111; }
  p, code, small, td, th { font-family: "JetBrains Mono", monospace; }
  small { color: #888; }
  section { border: 1px solid #333; margin-top: 18px; padding: 18px; background: #050505; }
  img { width: 100%; border: 1px solid #333; background: #000; }
  table { width: 100%; border-collapse: collapse; margin-top: 12px; font-size: 12px; }
  th, td { border: 1px solid #333; padding: 8px; text-align: left; vertical-align: top; }
  th { color: #888; text-transform: uppercase; }
  pre { white-space: pre-wrap; overflow-wrap: anywhere; border: 1px solid #333; padding: 12px; background: #000; color: #fff; font-size: 11px; }
</style>
</head>
<body>
<main>
  <header>
    <small>NEXUSINTEL / TACTICAL REPORT</small>
    <h1>Intelligence Graph Export</h1>
    <p>Investigation: ${escapeHtml(investigationId || "local")}</p>
    <p>Generated: ${escapeHtml(generatedAt)}</p>
  </header>
  <section>
    <h2>Visual Link Analysis</h2>
    ${imageData ? `<img src="${imageData}" alt="Current graph canvas" />` : `<p>No graph image captured.</p>`}
  </section>
  <section>
    <h2>Entities</h2>
    <table><thead><tr><th>Type</th><th>Label</th><th>Value</th><th>Confidence</th></tr></thead><tbody>${rows}</tbody></table>
  </section>
  <section>
    <h2>Relationships</h2>
    <table><thead><tr><th>Source</th><th>Label</th><th>Target</th><th>Confidence</th></tr></thead><tbody>${edgeRows}</tbody></table>
  </section>
  <section>
    <h2>Structured Graph JSON</h2>
    <pre>${graphJson}</pre>
  </section>
</main>
</body>
</html>`;
}

function nodeElement(node: GraphNode): cytoscape.ElementDefinition {
  const confidence = String(node.nodeProperties.confidence || "medium");
  return {
    group: "nodes",
    data: {
      id: node.id,
      label: `[${node.nodeIcon || "NX"}] ${node.nodeLabel}`,
      rawLabel: node.nodeLabel,
      nodeType: node.nodeType,
      value: String(node.nodeProperties.value || node.nodeLabel),
      confidence,
      nodeShape: cyShape(node.nodeShape),
      flag: node.nodeFlag || "",
    },
    position: { x: node.x, y: node.y },
    classes: `entity shape-${node.nodeShape} ${confidence === "low" ? "low-confidence" : ""}`,
  };
}

function edgeElement(edge: GraphEdge, runningNodeId: string | null, faded = false): cytoscape.ElementDefinition {
  const confidence = edge.confidence_level || 60;
  return {
    group: "edges",
    data: {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      label: edge.label,
      confidence_level: confidence,
      width: Math.max(1, confidence / 38),
    },
    classes: `edge ${confidence < 50 ? "low-confidence" : ""} ${runningNodeId && edge.source === runningNodeId ? "running-flow" : ""} ${faded ? "faded" : ""}`,
  };
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
  onSystemLog,
  onOracleNode,
  searchTarget,
  setSearchTarget,
  reconMode,
  setReconMode,
  onLaunch,
  isLaunching,
  terminalOpen,
  setTerminalOpen,
  dataPanelOpen,
  setDataPanelOpen,
}: GraphCanvasProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const cyRef = useRef<cytoscape.Core | null>(null);
  const pollers = useRef<Record<string, number>>({});
  const dashAnimation = useRef<number | null>(null);
  const graphNodesRef = useRef<GraphNode[]>([]);
  const graphEdgesRef = useRef<GraphEdge[]>([]);
  const apiNodesRef = useRef<Map<string, ApiGraphNode>>(new Map());
  const incomingIdsRef = useRef<Set<string>>(new Set());
  const historyStack = useRef<Array<{ nodes: GraphNode[]; edges: GraphEdge[] }>>([]);
  const redoStack = useRef<Array<{ nodes: GraphNode[]; edges: GraphEdge[] }>>([]);
  const suppressNextPropHistory = useRef(false);
  const hasFitRef = useRef(false);
  const [graphNodes, setGraphNodes] = useState<GraphNode[]>([]);
  const [graphEdges, setGraphEdges] = useState<GraphEdge[]>([]);
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("force");
  const [timelineMode, setTimelineMode] = useState(false);
  const [highlightType, setHighlightType] = useState("all");
  const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null);
  const [contextTab, setContextTab] = useState<ContextTab>("transforms");
  const [runningTask, setRunningTask] = useState<string | null>(null);
  const [runningNodeId, setRunningNodeId] = useState<string | null>(null);
  const [dropHint, setDropHint] = useState(false);

  const selectedStrictNode = useMemo(() => graphNodes.find((node) => node.id === selectedNode?.id) || null, [graphNodes, selectedNode?.id]);

  const resizeGraph = useCallback((fit = false) => {
    window.requestAnimationFrame(() => {
      const cy = cyRef.current;
      if (!cy) return;
      cy.resize();
      if (fit && cy.nodes().length) cy.fit(undefined, 96);
    });
  }, []);

  const pushHistory = useCallback((snapshot?: { nodes: GraphNode[]; edges: GraphEdge[] }) => {
    const cloned = snapshot || cloneState(graphNodesRef.current, graphEdgesRef.current);
    if (!cloned.nodes.length && !cloned.edges.length) return;
    historyStack.current = [...historyStack.current.slice(-(HISTORY_LIMIT - 1)), cloned];
    redoStack.current = [];
  }, []);

  const restoreState = useCallback(
    (snapshot: { nodes: GraphNode[]; edges: GraphEdge[] }, message: string) => {
      setGraphNodes(snapshot.nodes);
      setGraphEdges(snapshot.edges);
      onSystemLog?.(message);
      requestAnimationFrame(() => cyRef.current?.fit(undefined, 86));
    },
    [onSystemLog],
  );

  const undoGraph = useCallback(() => {
    const previous = historyStack.current.pop();
    if (!previous) return;
    redoStack.current = [...redoStack.current.slice(-(HISTORY_LIMIT - 1)), cloneState(graphNodesRef.current, graphEdgesRef.current)];
    restoreState(previous, "Graph state reverted.");
  }, [restoreState]);

  const redoGraph = useCallback(() => {
    const next = redoStack.current.pop();
    if (!next) return;
    historyStack.current = [...historyStack.current.slice(-(HISTORY_LIMIT - 1)), cloneState(graphNodesRef.current, graphEdgesRef.current)];
    restoreState(next, "Graph state restored.");
  }, [restoreState]);

  useEffect(() => {
    graphNodesRef.current = graphNodes;
    graphEdgesRef.current = graphEdges;
  }, [graphEdges, graphNodes]);

  useEffect(() => {
    apiNodesRef.current = new Map(nodes.map((node) => [node.id, node]));
  }, [nodes]);

  useEffect(() => {
    historyStack.current = [];
    redoStack.current = [];
    incomingIdsRef.current = new Set();
    hasFitRef.current = false;
  }, [investigationId]);

  useEffect(() => {
    const incomingIds = new Set(nodes.map((node) => node.id));
    const priorIds = incomingIdsRef.current;
    const changedAfterInitial = priorIds.size > 0 && (nodes.some((node) => !priorIds.has(node.id)) || [...priorIds].some((id) => !incomingIds.has(id)));
    if (changedAfterInitial && !suppressNextPropHistory.current) pushHistory();
    suppressNextPropHistory.current = false;

    setGraphNodes((previous) => {
      const previousById = new Map(previous.map((node) => [node.id, node]));
      const siblingCounts = new Map<string, number>();
      return nodes.map((node, index) => {
        const parentEdge = edges.find((edge) => edge.target === node.id && previousById.has(edge.source));
        let parentPosition: { x: number; y: number; siblingIndex: number } | undefined;
        if (!previousById.has(node.id) && parentEdge) {
          const parent = previousById.get(parentEdge.source);
          const cyParent = cyRef.current?.getElementById(parentEdge.source);
          const siblingIndex = siblingCounts.get(parentEdge.source) || 0;
          siblingCounts.set(parentEdge.source, siblingIndex + 1);
          parentPosition = {
            x: cyParent?.length ? cyParent.position("x") : parent?.x || 260,
            y: cyParent?.length ? cyParent.position("y") : parent?.y || 260,
            siblingIndex,
          };
        }
        return strictNodeFromApi(node, previousById.get(node.id), index, parentPosition);
      });
    });
    setGraphEdges(edges.map(strictEdgeFromApi));
    incomingIdsRef.current = incomingIds;
  }, [edges, nodes, pushHistory]);

  const selectStrictNode = useCallback(
    (node: GraphNode | null) => {
      if (!node) {
        onSelectNode(null);
        return;
      }
      onSelectNode(apiNodesRef.current.get(node.id) || apiNodeFromStrict(node));
      setDataPanelOpen(true);
    },
    [onSelectNode, setDataPanelOpen],
  );

  const runLayout = useCallback((mode: LayoutMode = layoutMode, fit = true) => {
    const cy = cyRef.current;
    if (!cy || !cy.nodes().length) return;
    const common = { animate: true, animationDuration: 520, animationEasing: "ease-out", fit, padding: 92 };
    if (mode === "tree") {
      cy.layout({ name: "breadthfirst", directed: true, circle: false, spacingFactor: 1.6, avoidOverlap: true, ...common }).run();
      return;
    }
    if (mode === "circular") {
      cy.layout({ name: "concentric", minNodeSpacing: 82, spacingFactor: 1.25, concentric: (node) => (node.indegree(false) ? 1 : 3), levelWidth: () => 1, ...common }).run();
      return;
    }
    cy.layout({ name: "cose", nodeRepulsion: 9800, idealEdgeLength: 144, edgeElasticity: 80, gravity: 0.22, numIter: 900, ...common }).run();
  }, [layoutMode]);

  const pollGraphUntilComplete = useCallback(
    (taskId: string) => {
      if (pollers.current[taskId]) window.clearInterval(pollers.current[taskId]);
      const refresh = async () => {
        try {
          const graphPayload = await apiJson(`/api/v1/tasks/${taskId}/graph`);
          onGraphUpdate(normalizeGraphPayload(graphPayload.data));
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
      };
      void refresh();
      pollers.current[taskId] = window.setInterval(refresh, 1500);
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
          body: JSON.stringify({ investigation_id: investigationId, node_id: node.id, transform, mode: reconMode }),
        });
        setRunningTask(payload.data.task_id);
        onTaskStart(payload.data.task_id, transform, apiNodesRef.current.get(node.id) || apiNodeFromStrict(node));
        pollGraphUntilComplete(payload.data.task_id);
      } catch (error) {
        setRunningTask(null);
        setRunningNodeId(null);
        onError(error instanceof Error ? error.message : "Transform failed");
      }
    },
    [investigationId, onError, onTaskStart, pollGraphUntilComplete, reconMode],
  );

  const deleteNode = useCallback(
    async (node: GraphNode) => {
      if (!investigationId) return;
      setContextMenu(null);
      pushHistory();
      setGraphNodes((previous) => previous.filter((item) => item.id !== node.id));
      setGraphEdges((previous) => previous.filter((edge) => edge.source !== node.id && edge.target !== node.id));
      cyRef.current?.getElementById(node.id).remove();
      if (selectedNode?.id === node.id) onSelectNode(null);
      suppressNextPropHistory.current = true;
      try {
        const payload = await apiJson(`/api/v1/investigations/${investigationId}/entities/${node.id}`, { method: "DELETE" });
        onGraphUpdate(normalizeGraphPayload(payload.data.graph));
      } catch (error) {
        onError(error instanceof Error ? error.message : "Delete failed");
      }
    },
    [investigationId, onError, onGraphUpdate, onSelectNode, pushHistory, selectedNode?.id],
  );

  const addEntityFromDrop = useCallback(
    async (kind: string, point: { x: number; y: number }) => {
      if (!investigationId) {
        onError("Create or select an investigation before adding an entity.");
        return;
      }
      const value = window.prompt(`Value for ${kind}`);
      if (!value?.trim()) return;
      pushHistory();
      try {
        const payload = await apiJson("/api/v1/entities", {
          method: "POST",
          body: JSON.stringify({
            investigation_id: investigationId,
            type: kind,
            label: value.trim(),
            value: value.trim(),
            source_id: selectedNode?.id || null,
            relationship_type: selectedNode ? "manual_pivot" : "manual_seed",
            data: { created_from: "graph_drag_drop", x: point.x, y: point.y, parent: selectedNode?.id || null },
          }),
        });
        onGraphUpdate(normalizeGraphPayload(payload.data.graph));
      } catch (error) {
        onError(error instanceof Error ? error.message : "Failed to add dropped entity");
      }
    },
    [investigationId, onError, onGraphUpdate, pushHistory, selectedNode?.id],
  );

  const addEntityFromToolbar = useCallback(() => {
    const kind = window.prompt("Entity type", "username")?.trim().toLowerCase();
    if (!kind) return;
    const pan = cyRef.current?.pan() || { x: 0, y: 0 };
    const zoom = cyRef.current?.zoom() || 1;
    const rect = containerRef.current?.getBoundingClientRect();
    const renderedCenter = { x: (rect?.width || 900) / 2, y: (rect?.height || 560) / 2 };
    addEntityFromDrop(kind, { x: (renderedCenter.x - pan.x) / zoom, y: (renderedCenter.y - pan.y) / zoom });
  }, [addEntityFromDrop]);

  const exportReport = useCallback(() => {
    const image = cyRef.current?.png({ full: true, scale: 2, bg: "#000000" }) || "";
    const html = reportHtml(graphNodesRef.current, graphEdgesRef.current, image, investigationId);
    const blob = new Blob([html], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `nexusintel-report-${new Date().toISOString().replace(/[:.]/g, "-")}.html`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    onSystemLog?.("Intelligence report exported.");
  }, [investigationId, onSystemLog]);

  useEffect(() => {
    if (!containerRef.current || cyRef.current) return;
    cyRef.current = cytoscape({
      container: containerRef.current,
      wheelSensitivity: 0.14,
      minZoom: 0.18,
      maxZoom: 2.8,
      pixelRatio: "auto",
      style: [
        {
          selector: "node",
          style: {
            width: 76,
            height: 76,
            shape: "data(nodeShape)",
            "background-color": "#111111",
            "background-opacity": 1,
            "border-width": 1,
            "border-color": "#ffffff",
            color: "#ffffff",
            label: "data(label)",
            "font-family": "JetBrains Mono, SFMono-Regular, Consolas, monospace",
            "font-size": 9,
            "font-weight": 600,
            "text-wrap": "wrap",
            "text-max-width": 132,
            "text-valign": "bottom",
            "text-halign": "center",
            "text-margin-y": 8,
            "overlay-opacity": 0,
            opacity: 1,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 2,
            "border-color": "#ffffff",
            "background-color": "#181818",
            "shadow-blur": 10,
            "shadow-color": "#ffffff",
            "shadow-opacity": 0.28,
          },
        },
        {
          selector: "node.low-confidence",
          style: { "border-style": "dashed", "border-color": "#888888", color: "#888888" },
        },
        {
          selector: "node.processing",
          style: { "shadow-blur": 14, "shadow-color": "#ffffff", "shadow-opacity": 0.44, "border-width": 2 },
        },
        {
          selector: "edge",
          style: {
            width: "data(width)",
            "line-color": "#666666",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#666666",
            "curve-style": "bezier",
            label: "data(label)",
            color: "#888888",
            "font-family": "JetBrains Mono, SFMono-Regular, Consolas, monospace",
            "font-size": 8,
            "text-background-color": "#000000",
            "text-background-opacity": 1,
            "text-background-padding": 2,
            "overlay-opacity": 0,
          },
        },
        {
          selector: "edge.low-confidence",
          style: { "line-style": "dashed", "line-color": "#444444", "target-arrow-color": "#444444" },
        },

        {
          selector: ".faded",
          style: { opacity: 0.2 },
        },
        {
          selector: "edge.running-flow",
          style: {
            "line-style": "dashed",
            "line-dash-pattern": [8, 6],
            "line-color": "#ffffff",
            "target-arrow-color": "#ffffff",
            width: 1.4,
          },
        },
      ],
      layout: { name: "preset", fit: false },
    });

    const cy = cyRef.current;
    cy.on("tap", (event) => {
      if (event.target === cy) {
        setContextMenu(null);
        selectStrictNode(null);
      }
    });
    cy.on("tap", "node", (event) => {
      const strict = graphNodesRef.current.find((item) => item.id === event.target.id()) || null;
      selectStrictNode(strict);
      setContextMenu(null);
    });
    cy.on("cxttap", "node", (event) => {
      const strict = graphNodesRef.current.find((item) => item.id === event.target.id());
      if (!strict || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const rendered = event.renderedPosition || { x: rect.width / 2, y: rect.height / 2 };
      selectStrictNode(strict);
      setContextTab("transforms");
      setContextMenu({ x: rect.left + rendered.x, y: rect.top + rendered.y, node: strict });
    });
    cy.on("dragfree", "node", (event) => {
      const id = event.target.id();
      const position = event.target.position();
      setGraphNodes((previous) => previous.map((node) => (node.id === id ? { ...node, x: position.x, y: position.y } : node)));
    });

    return () => {
      Object.values(pollers.current).forEach((id) => window.clearInterval(id));
      pollers.current = {};
      if (dashAnimation.current) cancelAnimationFrame(dashAnimation.current);
      cy.destroy();
      cyRef.current = null;
    };
  }, [selectStrictNode]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver(() => resizeGraph(false));
    observer.observe(element);
    return () => observer.disconnect();
  }, [resizeGraph]);

  useEffect(() => {
    resizeGraph(false);
    const timer = window.setTimeout(() => resizeGraph(false), 340);
    return () => window.clearTimeout(timer);
  }, [dataPanelOpen, resizeGraph, terminalOpen, timelineMode]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.resize();
    const nodeMap = new Map(graphNodes.map((node) => [node.id, node]));
    const edgeMap = new Map(graphEdges.map((edge) => [edge.id, edge]));
    const typeById = new Map(graphNodes.map((node) => [node.id, node.nodeType]));

    cy.batch(() => {
      cy.nodes().forEach((node) => {
        if (!nodeMap.has(node.id())) node.remove();
      });
      cy.edges().forEach((edge) => {
        if (!edgeMap.has(edge.id())) edge.remove();
      });

      graphNodes.forEach((node) => {
        const existing = cy.getElementById(node.id);
        const element = nodeElement(node);
        const faded = highlightType !== "all" && node.nodeType !== highlightType;
        const classes = `${element.classes || ""} ${node.id === runningNodeId ? "processing" : ""} ${faded ? "faded" : ""}`.trim();
        if (existing.length) {
          existing.data(element.data || {});
          existing.classes(classes);
          if (!existing.grabbed()) existing.position({ x: node.x, y: node.y });
        } else {
          const added = cy.add(element);
          added.classes(classes);
          added.style("opacity", 0);
          added.animate({ style: { opacity: 1 }, position: { x: node.x, y: node.y } }, { duration: 360, easing: "ease-out" });
        }
      });

      graphEdges.forEach((edge) => {
        if (!cy.getElementById(edge.source).length || !cy.getElementById(edge.target).length) return;
        const existing = cy.getElementById(edge.id);
        const faded = highlightType !== "all" && typeById.get(edge.source) !== highlightType && typeById.get(edge.target) !== highlightType;
        const element = edgeElement(edge, runningNodeId, faded);
        if (existing.length) {
          existing.data(element.data || {});
          existing.classes(String(element.classes || ""));
        } else {
          const added = cy.add(element);
          added.style("opacity", 0);
          added.animate({ style: { opacity: 1 } }, { duration: 320, easing: "ease-out" });
        }
      });
    });

    if (!hasFitRef.current && graphNodes.length) {
      runLayout(layoutMode, true);
      hasFitRef.current = true;
    } else {
      resizeGraph(false);
    }
  }, [graphEdges, graphNodes, highlightType, layoutMode, resizeGraph, runLayout, runningNodeId]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().unselect();
    if (selectedNode) cy.getElementById(selectedNode.id).select();
  }, [selectedNode]);

  useEffect(() => {
    runLayout(layoutMode, true);
  }, [layoutMode, runLayout]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return undefined;
    if (!runningTask) return undefined;
    let offset = 0;
    const tick = () => {
      offset = (offset + 1) % 28;
      cy.edges(".running-flow").style("line-dash-offset", -offset);
      dashAnimation.current = requestAnimationFrame(tick);
    };
    dashAnimation.current = requestAnimationFrame(tick);
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


  useEffect(() => {
    const handleOracleCommand = (event: Event) => {
      const detail = (event as CustomEvent).detail || {};
      if (detail.type === "highlight_type" && detail.nodeType) setHighlightType(String(detail.nodeType));
      if (detail.type === "clear_highlight") setHighlightType("all");
    };
    window.addEventListener("nexus:oracle-command", handleOracleCommand);
    return () => window.removeEventListener("nexus:oracle-command", handleOracleCommand);
  }, []);

  useEffect(() => {
    const handleShortcut = (event: KeyboardEvent) => {
      if (!(event.ctrlKey || event.metaKey)) return;
      const key = event.key.toLowerCase();
      if (!["t", "z", "y"].includes(key)) return;
      event.preventDefault();
      if (key === "t") setTimelineMode((open) => !open);
      if (key === "z") undoGraph();
      if (key === "y") redoGraph();
    };
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [redoGraph, undoGraph]);

  const contextPosition = useMemo(() => {
    if (!contextMenu) return { x: 0, y: 0 };
    return {
      x: Math.max(10, Math.min(contextMenu.x, window.innerWidth - 342)),
      y: Math.max(10, Math.min(contextMenu.y, window.innerHeight - 390)),
    };
  }, [contextMenu]);

  return (
    <section className={dropHint ? "tactical-graph-shell drop-active" : "tactical-graph-shell"}>
      <header className="tactical-graph-toolbar">
        <div className="graph-toolbar-stats">
          <span className="micro-label">Visual Link Analysis</span>
          <strong>{graphNodes.length} entities</strong>
          <span>{graphEdges.length} relationships</span>
        </div>

        <form className="graph-launcher" onSubmit={onLaunch}>
          <Search size={15} />
          <input value={searchTarget} onChange={(event) => setSearchTarget(event.target.value)} placeholder="username, email, domain, IP, phone" />
          <select value={reconMode} onChange={(event) => setReconMode(event.target.value as "passive" | "standard" | "aggressive")}>
            <option value="passive">Passive</option>
            <option value="standard">Standard</option>
            <option value="aggressive">Aggressive</option>
          </select>
          <button className="graph-launch-button" type="submit" disabled={isLaunching}>
            <Radio size={14} />
            <span>{isLaunching ? "Running" : "Launch"}</span>
          </button>
        </form>

        <div className="entity-pipeline" aria-label="Entity palette">
          <button className="icon-button" type="button" onClick={addEntityFromToolbar} title="Add entity at canvas center">
            <Plus size={16} />
          </button>
          {PALETTE_TYPES.map((kind) => <EntityPaletteItem kind={kind} key={kind} />)}
        </div>

        <div className="graph-toolbar-controls">
          <div className="graph-smart-selector">
            <span>Highlight</span>
            <select value={highlightType} onChange={(event) => setHighlightType(event.target.value)}>
              <option value="all">All entities</option>
              <option value="username">Username</option>
              <option value="email">Email</option>
              <option value="domain">Domain</option>
              <option value="ip">IP address</option>
              <option value="phone">Phone</option>
              <option value="profile">Profile</option>
              <option value="platform">Platform</option>
            </select>
          </div>

          <div className="layout-switcher" aria-label="Graph layout modes">
            <button className={layoutMode === "tree" ? "active" : ""} type="button" onClick={() => setLayoutMode("tree")} title="Tree layout">
              <GitBranch size={14} />
              <span>Tree</span>
            </button>
            <button className={layoutMode === "circular" ? "active" : ""} type="button" onClick={() => setLayoutMode("circular")} title="Circular layout">
              <Crosshair size={14} />
              <span>Orbit</span>
            </button>
            <button className={layoutMode === "force" ? "active" : ""} type="button" onClick={() => setLayoutMode("force")} title="Force layout">
              <Network size={14} />
              <span>Force</span>
            </button>
          </div>

          <div className="tactical-graph-actions">
            <button className={timelineMode ? "icon-button active" : "icon-button"} type="button" onClick={() => setTimelineMode((open) => !open)} title="Timeline mode (Ctrl+T)">
              <Clock3 size={16} />
            </button>
            <button className="icon-button" type="button" onClick={undoGraph} title="Undo graph state (Ctrl+Z)">
              <Undo2 size={16} />
            </button>
            <button className="icon-button" type="button" onClick={() => runLayout(layoutMode, true)} title="Re-layout current graph">
              <RotateCcw size={16} />
            </button>
            <button className="icon-button" type="button" onClick={() => cyRef.current?.fit(undefined, 90)} title="Fit graph">
              <Crosshair size={16} />
            </button>
            <button className={dataPanelOpen ? "icon-button active" : "icon-button"} type="button" onClick={() => setDataPanelOpen((open) => !open)} title="Toggle entity data panel">
              <PanelRight size={16} />
            </button>
            <button className={terminalOpen ? "icon-button active" : "icon-button"} type="button" onClick={() => setTerminalOpen((open) => !open)} title="Toggle terminal HUD">
              <PanelBottom size={16} />
            </button>
            <button className="graph-report-button" type="button" onClick={exportReport} title="Export Intelligence report">
              <Download size={15} />
              <span>Export</span>
            </button>
          </div>
        </div>
      </header>

      {timelineMode ? (
        <TimelineView nodes={graphNodes} edges={graphEdges} onSelectNode={selectStrictNode} />
      ) : (
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
            if (!kind || !containerRef.current) return;
            const rect = containerRef.current.getBoundingClientRect();
            const rendered = { x: event.clientX - rect.left, y: event.clientY - rect.top };
            const pan = cyRef.current?.pan() || { x: 0, y: 0 };
            const zoom = cyRef.current?.zoom() || 1;
            addEntityFromDrop(kind, { x: (rendered.x - pan.x) / zoom, y: (rendered.y - pan.y) / zoom });
          }}
        >
          {!graphNodes.length && (
            <div className="empty-graph">
              <Plus size={22} />
              <strong>No investigation graph loaded</strong>
              <span>Create or select a target, then drag entities into the canvas.</span>
            </div>
          )}
        </div>
      )}

      {contextMenu && (
        <div
          className="graph-context-menu"
          style={{ transform: `translate3d(${contextPosition.x}px, ${contextPosition.y}px, 0)` }}
          onClick={(event) => event.stopPropagation()}
        >
          <div className="context-node-card">
            <div className="context-node-mark">{contextMenu.node.nodeIcon || "NX"}</div>
            <div>
              <strong>{contextMenu.node.nodeLabel}</strong>
              <span>{contextMenu.node.nodeType} / {String(contextMenu.node.nodeProperties.confidence || "medium")}</span>
            </div>
          </div>

          {onOracleNode && (
            <button
              className="context-oracle"
              type="button"
              onClick={() => {
                const apiNode = apiNodesRef.current.get(contextMenu.node.id) || apiNodeFromStrict(contextMenu.node);
                setContextMenu(null);
                onOracleNode(apiNode);
              }}
            >
              <Network size={14} />
              <span>
                <strong>Ask Oracle</strong>
                <small>Analyze this node and suggest the next OSINT transform</small>
              </span>
            </button>
          )}
          <div className="context-tabs">
            <button className={contextTab === "transforms" ? "active" : ""} type="button" onClick={() => setContextTab("transforms")}>Transforms</button>
            <button className={contextTab === "playbooks" ? "active" : ""} type="button" onClick={() => setContextTab("playbooks")}>Playbooks</button>
          </div>
          <div className="context-actions">
            {(contextTab === "transforms" ? transformsFor(contextMenu.node) : playbooksFor(contextMenu.node)).map((action) => (
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
                <strong>Delete Entity</strong>
                <small>Remove this node and attached relationships from UI and API</small>
              </span>
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
