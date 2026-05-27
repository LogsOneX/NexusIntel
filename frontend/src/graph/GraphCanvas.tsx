import { type CSSProperties, type Dispatch, type FormEvent, type PointerEvent as ReactPointerEvent, type SetStateAction, type WheelEvent as ReactWheelEvent, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Maximize2, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import { getStudioNodeConfidence, getStudioNodeIcon, getStudioNodeRisk, getStudioNodeVisual, mapApiEdgeToStudioEdge, mapApiNodeToStudioNode } from "../lib/studioMappers";
import NodeActionPopover from "../components/graph/NodeActionPopover";
import type { TransformDefinition } from "../lib/types";
import { compatibleTransformsForNode } from "../lib/transformMatching";
import { clamp, fitBoundsToViewport, screenToWorld, worldToScreen, zoomToCursor, type ViewportPoint } from "./viewportMath";
import { graphPositionStorageKey, readGraphPositions, writeGraphPositions } from "./positionStore";

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
  created_at?: string;
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
  leads?: unknown[];
  noise?: unknown[];
  compliance?: unknown[];
  metadata?: Record<string, unknown>;
};

type LayoutMode = "manual" | "tree" | "circular" | "force";
type InteractionState =
  | { type: "node"; pointerId: number; target: HTMLElement; nodeId: string; offsetX: number; offsetY: number; startClientX: number; startClientY: number; hasDragged: boolean }
  | { type: "pan"; pointerId: number; target: HTMLElement; startClientX: number; startClientY: number; startPan: ViewportPoint; hasDragged: boolean };

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
  searchTarget?: string;
  setSearchTarget?: Dispatch<SetStateAction<string>>;
  reconMode?: "passive" | "standard" | "aggressive";
  setReconMode?: Dispatch<SetStateAction<"passive" | "standard" | "aggressive">>;
  onLaunch?: (event: FormEvent<HTMLFormElement>) => void | Promise<void>;
  onAddSeed?: (value: string, mode: "passive" | "standard" | "aggressive") => void | Promise<void>;
  isLaunching?: boolean;
  terminalOpen?: boolean;
  setTerminalOpen?: Dispatch<SetStateAction<boolean>>;
  dataPanelOpen?: boolean;
  setDataPanelOpen?: Dispatch<SetStateAction<boolean>>;
  hideToolbar?: boolean;
  onOpenAddEntity?: (kind?: string) => void;
  onOpenImport?: () => void;
  transforms?: TransformDefinition[];
  transformLoading?: string | null;
  transformError?: string | null;
  onRunTransform?: (transformId: string, node: ApiGraphNode) => void;
  onOpenEvidenceVault?: (node?: ApiGraphNode) => void;
  onOpenTransformLibrary?: () => void;
  onMarkNoiseNode?: (node: ApiGraphNode) => void;
  onRunCorrelation?: () => void;
};

const NODE_WIDTH = 120;
const NODE_HEIGHT = 130;
const MIN_ZOOM = 0.25;
const MAX_ZOOM = 2.5;
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

const NODE_ICON_PATHS: Record<string, string> = {
  identity: `<circle cx="32" cy="21" r="9"/><path d="M15 53c3-12 10-18 17-18s14 6 17 18"/>`,
  fingerprint: `<path d="M20 28a12 12 0 0124 0v4"/><path d="M14 34v-6a18 18 0 0136 0v5"/><path d="M25 56c-3-8-3-16-1-24a8 8 0 0116 0c1 8-1 15-5 21"/><path d="M32 30v10"/>`,
  mail: `<rect x="10" y="18" width="44" height="30" rx="2"/><path d="M12 21l20 16 20-16"/>`,
  phone: `<path d="M21 10h22v44H21z"/><path d="M29 47h6"/>`,
  globe: `<circle cx="32" cy="32" r="22"/><path d="M10 32h44M32 10c8 8 8 36 0 44M32 10c-8 8-8 36 0 44"/>`,
  link: `<path d="M25 23l-5 5a10 10 0 0014 14l5-5"/><path d="M39 41l5-5a10 10 0 00-14-14l-5 5"/><path d="M25 39l14-14"/>`,
  server: `<rect x="12" y="14" width="40" height="12" rx="2"/><rect x="12" y="30" width="40" height="12" rx="2"/><rect x="12" y="46" width="40" height="8" rx="2"/><path d="M20 20h4M20 36h4M20 50h4"/>`,
  pin: `<path d="M32 56s18-18 18-32A18 18 0 1014 24c0 14 18 32 18 32z"/><circle cx="32" cy="24" r="6"/>`,
  image: `<rect x="12" y="16" width="40" height="32" rx="3"/><path d="M18 42l10-10 8 8 5-5 7 7"/><circle cx="42" cy="25" r="4"/>`,
  wallet: `<path d="M10 20h44v30H10z"/><path d="M44 30h12v12H44z"/><path d="M22 42V18h24"/>`,
  transaction: `<path d="M12 22h34l-8-8M46 22l-8 8"/><path d="M52 42H18l8-8M18 42l8 8"/>`,
  file: `<path d="M18 10h21l9 9v35H18z"/><path d="M39 10v12h9M25 32h15M25 41h12"/>`,
  alert: `<path d="M32 9l25 44H7z"/><path d="M32 24v13M32 45h.1"/>`,
  target: `<circle cx="32" cy="32" r="20"/><circle cx="32" cy="32" r="8"/><path d="M32 6v10M32 48v10M6 32h10M48 32h10"/>`,
};

const HIDDEN_NODE_TYPES = new Set([
  "guardrail", "compliance", "skipped_check", "legal_note", "policy", "policy_notice", "blocked_transform", "prohibited_probe_notice",
  "noise", "soft_404", "auth_wall_only", "generic_login_page", "parked_domain", "registrar_privacy_noise",
]);

const CANDIDATE_NODE_TYPES = new Set([
  "profile_candidate", "candidate_profile", "candidate_url_only", "username_candidate", "email_candidate", "phone_deeplink_candidate", "possible_profile", "possible_same_actor",
]);

function upperSnake(value: string): string {
  const normalized = value.replace(/([a-z0-9])([A-Z])/g, "$1_$2").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  return (normalized || "RELATED_TO").toUpperCase();
}

function confidenceScore(value?: string): number | undefined {
  const raw = String(value || "").toLowerCase();
  if (["confirmed", "verified", "high", "strong", "success", "true"].includes(raw)) return 90;
  if (["medium", "observed", "probable"].includes(raw)) return 60;
  if (["low", "weak", "candidate", "false"].includes(raw)) return 30;
  return undefined;
}

function isGraphVisible(node: ApiGraphNode): boolean {
  const type = String(node.type || "").toLowerCase();
  const data = node.data || {};
  const artifactClass = String(data.artifact_class || data.classification || "").toLowerCase();
  const visibility = String(data.graph_visibility || "").toLowerCase();
  if (HIDDEN_NODE_TYPES.has(type) || HIDDEN_NODE_TYPES.has(artifactClass) || HIDDEN_NODE_TYPES.has(visibility)) return false;
  if (CANDIDATE_NODE_TYPES.has(type) || CANDIDATE_NODE_TYPES.has(artifactClass) || visibility === "candidate_bin") return false;
  return true;
}

function compactLabel(value: string): string {
  const clean = String(value || "").replace(/\s+/g, " ").trim();
  if (clean.length <= 28) return clean;
  if (clean.includes("@")) {
    const [local, domain] = clean.split("@");
    return `${local.slice(0, 12)}...@${(domain || "").slice(0, 12)}`;
  }
  return `${clean.slice(0, 25)}...`;
}

function nodeSource(node: ApiGraphNode): string {
  return String(node.source || node.data?.source || node.data?.adapter_id || "graph");
}

function positionFor(index: number, total: number, width: number, height: number, mode: LayoutMode): ViewportPoint {
  const centerX = Math.max(440, width / 2);
  const centerY = Math.max(280, height / 2);
  if (mode === "tree") {
    const columns = Math.max(1, Math.ceil(Math.sqrt(total || 1)));
    return { x: 155 + (index % columns) * 190, y: 118 + Math.floor(index / columns) * 150 };
  }
  if (mode === "circular") {
    const radius = Math.max(190, Math.min(width, height) * 0.32);
    const angle = total <= 1 ? -Math.PI / 2 : (index / total) * Math.PI * 2 - Math.PI / 2;
    return { x: centerX + Math.cos(angle) * radius - NODE_WIDTH / 2, y: centerY + Math.sin(angle) * radius - 32 };
  }
  const radius = 92 + Math.sqrt(index + 1) * 58;
  const angle = index * GOLDEN_ANGLE;
  return { x: centerX + Math.cos(angle) * radius - NODE_WIDTH / 2, y: centerY + Math.sin(angle) * radius - 32 };
}

function graphNodeForReport(node: ApiGraphNode, position: ViewportPoint): GraphNode {
  return {
    id: node.id,
    nodeType: node.type,
    nodeLabel: node.label || node.value || node.type,
    nodeProperties: { ...(node.data || {}), value: node.value, source: node.source || "graph", confidence: node.confidence || "medium", confidence_level: getStudioNodeConfidence(node), created_at: node.created_at || new Date().toISOString() },
    nodeShape: "circle",
    x: position.x,
    y: position.y,
    nodeIcon: getStudioNodeIcon(node.type),
    nodeFlag: node.confidence === "low" ? "LOW" : null,
  };
}

function graphEdgeForReport(edge: ApiGraphEdge): GraphEdge {
  return { id: edge.id, source: edge.source, target: edge.target, label: upperSnake(edge.type), confidence_level: Number(edge.confidence_level || edge.data?.confidence_score || confidenceScore(edge.confidence) || 60), created_at: edge.created_at || String(edge.data?.created_at || "") };
}

function escapeHtml(value: unknown): string {
  return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

function reportHtml(nodes: GraphNode[], edges: GraphEdge[], investigationId: string | null): string {
  const generatedAt = new Date().toISOString();
  const rows = nodes.map((node) => `<tr><td>${escapeHtml(node.nodeType)}</td><td>${escapeHtml(node.nodeLabel)}</td><td>${escapeHtml(node.nodeProperties.value)}</td><td>${escapeHtml(node.nodeProperties.confidence_level || "")}</td></tr>`).join("");
  const edgeRows = edges.map((edge) => `<tr><td>${escapeHtml(edge.source)}</td><td>${escapeHtml(edge.label)}</td><td>${escapeHtml(edge.target)}</td><td>${escapeHtml(edge.confidence_level || "")}</td></tr>`).join("");
  const graphJson = escapeHtml(JSON.stringify({ nodes, edges }, null, 2));
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>NexusIntel Intelligence Report</title><style>body{margin:0;background:#0A0A0B;color:#E0E0E3;font-family:Inter,Arial,sans-serif}main{max-width:1160px;margin:0 auto;padding:32px}header,section{border:1px solid #2D2D30;background:#141416;margin:0 0 18px;padding:18px}h1,h2{margin:0 0 12px}small,td,th,pre{font-family:"JetBrains Mono",monospace}table{width:100%;border-collapse:collapse;font-size:12px}td,th{border:1px solid #2D2D30;padding:8px;text-align:left}pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#0F0F11;padding:12px}</style></head><body><main><header><small>NEXUSINTEL / STUDIO GRAPH EXPORT</small><h1>Intelligence Graph Export</h1><p>Investigation: ${escapeHtml(investigationId || "local")}</p><p>Generated: ${escapeHtml(generatedAt)}</p></header><section><h2>Entities</h2><table><thead><tr><th>Type</th><th>Label</th><th>Value</th><th>Confidence</th></tr></thead><tbody>${rows}</tbody></table></section><section><h2>Relationships</h2><table><thead><tr><th>Source</th><th>Label</th><th>Target</th><th>Confidence</th></tr></thead><tbody>${edgeRows}</tbody></table></section><section><h2>Structured Graph JSON</h2><pre>${graphJson}</pre></section></main></body></html>`;
}

function isTypingTarget(target: EventTarget | null): boolean {
  const element = target as HTMLElement | null;
  return element?.tagName === "INPUT" || element?.tagName === "TEXTAREA" || element?.tagName === "SELECT" || Boolean(element?.isContentEditable);
}

export default function GraphCanvas({
  investigationId,
  nodes,
  edges,
  selectedNode,
  onSelectNode,
  onSystemLog,
  setDataPanelOpen,
  onOpenAddEntity,
  onOpenImport,
  transforms = [],
  transformLoading,
  transformError,
  onRunTransform,
  onOpenEvidenceVault,
  onOpenTransformLibrary,
  onMarkNoiseNode,
  onRunCorrelation,
}: GraphCanvasProps) {
  const stageRef = useRef<HTMLDivElement | null>(null);
  const interactionRef = useRef<InteractionState | null>(null);
  const suppressClickNodeRef = useRef<string | null>(null);
  const lastTransformMenuLogRef = useRef<string | null>(null);
  const spaceDownRef = useRef(false);
  const positionsRef = useRef<Record<string, ViewportPoint>>({});
  const panRef = useRef<ViewportPoint>({ x: 0, y: 0 });
  const zoomRef = useRef(1);

  const [positions, setPositions] = useState<Record<string, ViewportPoint>>({});
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("force");
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState<ViewportPoint>({ x: 0, y: 0 });
  const [draggingNodeId, setDraggingNodeId] = useState<string | null>(null);
  const [panning, setPanning] = useState(false);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const [actionMenu, setActionMenu] = useState<{ nodeId: string; mode: "compact" | "full" } | null>(null);
  const [confirmNoiseNodeId, setConfirmNoiseNodeId] = useState<string | null>(null);
  const [multiSelectedIds, setMultiSelectedIds] = useState<Set<string>>(() => new Set());
  const [hiddenNodeIds, setHiddenNodeIds] = useState<Set<string>>(() => new Set());
  const [showCandidates, setShowCandidates] = useState(false);
  const [showSignals, setShowSignals] = useState(true);
  const [minConfidence, setMinConfidence] = useState(0);

  const visibleNodes = useMemo(() => nodes.filter((node) => {
    if (hiddenNodeIds.has(node.id)) return false;
    const data = node.data || {};
    const visibility = String(data.graph_visibility || "").toLowerCase();
    const artifactClass = String(data.artifact_class || data.classification || "").toLowerCase();
    const type = String(node.type || "").toLowerCase();
    const isCandidate = CANDIDATE_NODE_TYPES.has(type) || CANDIDATE_NODE_TYPES.has(artifactClass) || visibility === "candidate_bin";
    const isSignal = visibility === "signal_badge" || artifactClass === "signal";
    if (isCandidate && !showCandidates) return false;
    if (isSignal && !showSignals) return false;
    if (!isCandidate && !isGraphVisible(node)) return false;
    if (getStudioNodeConfidence(node) < minConfidence) return false;
    return true;
  }), [hiddenNodeIds, minConfidence, nodes, showCandidates, showSignals]);
  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map((node) => node.id)), [visibleNodes]);
  const visibleEdges = useMemo(() => edges.filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)), [edges, visibleNodeIds]);
  const studioNodes = useMemo(() => visibleNodes.map((node, index) => ({ api: node, ui: mapApiNodeToStudioNode(node, index) })), [visibleNodes]);
  const studioEdges = useMemo(() => visibleEdges.map((edge, index) => ({ api: edge, ui: mapApiEdgeToStudioEdge(edge, index) })), [visibleEdges]);
  const selectedId = selectedNode?.id || null;
  const positionKey = useMemo(() => graphPositionStorageKey(investigationId), [investigationId]);

  useEffect(() => { positionsRef.current = positions; }, [positions]);
  useEffect(() => { panRef.current = pan; }, [pan]);
  useEffect(() => { zoomRef.current = zoom; }, [zoom]);

  const persistPositions = useCallback((nextPositions: Record<string, ViewportPoint> = positionsRef.current) => {
    writeGraphPositions(positionKey, nextPositions);
  }, [positionKey]);

  const setViewport = useCallback((nextPan: ViewportPoint, nextZoom: number) => {
    const cleanZoom = clamp(nextZoom, MIN_ZOOM, MAX_ZOOM);
    const cleanPan = { x: Number.isFinite(nextPan.x) ? nextPan.x : 0, y: Number.isFinite(nextPan.y) ? nextPan.y : 0 };
    panRef.current = cleanPan;
    zoomRef.current = cleanZoom;
    setPan(cleanPan);
    setZoom(cleanZoom);
  }, []);

  const applyLayout = useCallback((mode: LayoutMode = layoutMode) => {
    const rect = stageRef.current?.getBoundingClientRect();
    const width = rect?.width || 1240;
    const height = rect?.height || 760;
    setLayoutMode(mode);
    if (mode === "manual") {
      persistPositions();
      onSystemLog?.("Graph layout switched to manual; dragged node positions preserved.");
      return;
    }
    const next = Object.fromEntries(visibleNodes.map((node, index) => [node.id, positionFor(index, visibleNodes.length, width, height, mode)]));
    positionsRef.current = next;
    setPositions(next);
    persistPositions(next);
    onSystemLog?.(`Graph layout switched to ${mode}.`);
  }, [layoutMode, onSystemLog, persistPositions, visibleNodes]);

  useEffect(() => {
    const stored = readGraphPositions(positionKey);
    setPositions((current) => {
      const rect = stageRef.current?.getBoundingClientRect();
      const width = rect?.width || 1240;
      const height = rect?.height || 760;
      let changed = false;
      const next = { ...stored, ...current };
      visibleNodes.forEach((node, index) => {
        if (!next[node.id]) {
          const dataX = Number(node.data?.x);
          const dataY = Number(node.data?.y);
          next[node.id] = Number.isFinite(dataX) && Number.isFinite(dataY) ? { x: dataX, y: dataY } : positionFor(index, visibleNodes.length, width, height, layoutMode === "manual" ? "force" : layoutMode);
          changed = true;
        }
      });
      Object.keys(next).forEach((id) => {
        if (!visibleNodeIds.has(id)) {
          delete next[id];
          changed = true;
        }
      });
      positionsRef.current = next;
      if (changed) writeGraphPositions(positionKey, next);
      return changed || Object.keys(current).length === 0 ? next : current;
    });
  }, [layoutMode, positionKey, visibleNodeIds, visibleNodes]);

  const screenToWorldPoint = useCallback((clientX: number, clientY: number): ViewportPoint => {
    const rect = stageRef.current?.getBoundingClientRect();
    if (!rect) return { x: 0, y: 0 };
    return screenToWorld(clientX, clientY, rect, panRef.current, zoomRef.current);
  }, []);

  const fitGraph = useCallback(() => {
    const rect = stageRef.current?.getBoundingClientRect();
    if (!rect || !visibleNodes.length) {
      setViewport({ x: 0, y: 0 }, 1);
      return;
    }
    const activePositions = visibleNodes.map((node, index) => positionsRef.current[node.id] || positionFor(index, visibleNodes.length, rect.width, rect.height, layoutMode));
    const viewport = fitBoundsToViewport({ positions: activePositions, rect, nodeWidth: NODE_WIDTH, nodeHeight: NODE_HEIGHT, padding: 120, minZoom: MIN_ZOOM, maxZoom: MAX_ZOOM });
    setViewport(viewport.pan, viewport.zoom);
    onSystemLog?.("Graph viewport fitted to visible entities.");
  }, [layoutMode, onSystemLog, setViewport, visibleNodes]);

  const zoomAt = useCallback((clientX: number, clientY: number, nextZoom: number) => {
    const rect = stageRef.current?.getBoundingClientRect();
    if (!rect) return;
    const viewport = zoomToCursor({ clientX, clientY, rect, pan: panRef.current, zoom: zoomRef.current, nextZoom: clamp(nextZoom, MIN_ZOOM, MAX_ZOOM) });
    setViewport(viewport.pan, viewport.zoom);
  }, [setViewport]);

  const zoomAtCenter = useCallback((factor: number) => {
    const rect = stageRef.current?.getBoundingClientRect();
    if (!rect) return;
    zoomAt(rect.left + rect.width / 2, rect.top + rect.height / 2, zoomRef.current * factor);
  }, [zoomAt]);

  const resetZoom = useCallback(() => {
    setViewport({ x: 0, y: 0 }, 1);
    onSystemLog?.("Graph zoom reset to 100%.");
  }, [onSystemLog, setViewport]);

  const exportGraph = useCallback(() => {
    const reportNodes = visibleNodes.map((node, index) => graphNodeForReport(node, positionsRef.current[node.id] || positionFor(index, visibleNodes.length, 1240, 760, layoutMode)));
    const reportEdges = visibleEdges.map(graphEdgeForReport);
    const blob = new Blob([reportHtml(reportNodes, reportEdges, investigationId)], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `nexusintel-graph-${investigationId || "local"}.html`;
    link.click();
    URL.revokeObjectURL(url);
    onSystemLog?.("Graph report exported from Studio renderer.");
  }, [investigationId, layoutMode, onSystemLog, visibleEdges, visibleNodes]);

  useEffect(() => {
    const handleFit = () => fitGraph();
    const handleLayout = (event: Event) => applyLayout(((event as CustomEvent<{ mode?: LayoutMode }>).detail?.mode || "force") as LayoutMode);
    const handleExport = () => exportGraph();
    window.addEventListener("nexus:graph-fit", handleFit);
    window.addEventListener("nexus:graph-layout", handleLayout);
    window.addEventListener("nexus:graph-export", handleExport);
    return () => {
      window.removeEventListener("nexus:graph-fit", handleFit);
      window.removeEventListener("nexus:graph-layout", handleLayout);
      window.removeEventListener("nexus:graph-export", handleExport);
    };
  }, [applyLayout, exportGraph, fitGraph]);

  useEffect(() => {
    const onPointerMove = (event: PointerEvent) => {
      const interaction = interactionRef.current;
      if (!interaction || interaction.pointerId !== event.pointerId) return;
      if (interaction.type === "node") {
        const world = screenToWorldPoint(event.clientX, event.clientY);
        const movement = Math.hypot(event.clientX - interaction.startClientX, event.clientY - interaction.startClientY);
        if (movement > 3) interaction.hasDragged = true;
        const nextPosition = { x: world.x - interaction.offsetX, y: world.y - interaction.offsetY };
        setPositions((current) => {
          const next = { ...current, [interaction.nodeId]: nextPosition };
          positionsRef.current = next;
          return next;
        });
        if (interaction.hasDragged) setLayoutMode("manual");
        return;
      }
      const movement = Math.hypot(event.clientX - interaction.startClientX, event.clientY - interaction.startClientY);
      if (movement > 3) interaction.hasDragged = true;
      setViewport({ x: interaction.startPan.x + event.clientX - interaction.startClientX, y: interaction.startPan.y + event.clientY - interaction.startClientY }, zoomRef.current);
    };

    const onPointerUp = (event: PointerEvent) => {
      const interaction = interactionRef.current;
      if (!interaction || interaction.pointerId !== event.pointerId) return;
      try { interaction.target.releasePointerCapture(event.pointerId); } catch { /* ignored */ }
      if (interaction.type === "node") {
        if (interaction.hasDragged) suppressClickNodeRef.current = interaction.nodeId;
        persistPositions();
        setDraggingNodeId(null);
      } else {
        setPanning(false);
      }
      interactionRef.current = null;
    };

    window.addEventListener("pointermove", onPointerMove);
    window.addEventListener("pointerup", onPointerUp);
    window.addEventListener("pointercancel", onPointerUp);
    return () => {
      window.removeEventListener("pointermove", onPointerMove);
      window.removeEventListener("pointerup", onPointerUp);
      window.removeEventListener("pointercancel", onPointerUp);
    };
  }, [persistPositions, screenToWorldPoint, setViewport]);

  const nodeById = useMemo(() => new Map(studioNodes.map((node) => [node.api.id, node])), [studioNodes]);
  const actionNode = actionMenu ? nodeById.get(actionMenu.nodeId) || null : null;
  const actionTransforms = useMemo(() => {
    return compatibleTransformsForNode(transforms, actionNode?.api || null);
  }, [actionNode, transforms]);
  const actionPosition = actionNode ? positions[actionNode.api.id] : null;
  const menuStyle = actionPosition ? (() => {
    const rect = stageRef.current?.getBoundingClientRect();
    const width = rect?.width || 1200;
    const height = rect?.height || 760;
    const point = worldToScreen(actionPosition.x + NODE_WIDTH + 14, actionPosition.y + 4, pan, zoom);
    const menuWidth = actionMenu?.mode === "full" ? 380 : 330;
    const menuHeight = actionMenu?.mode === "full" ? 520 : 390;
    return {
      left: clamp(point.x, 16, Math.max(16, width - menuWidth - 16)),
      top: clamp(point.y, 12, Math.max(12, height - menuHeight - 16)),
    };
  })() : undefined;
  const confirmNoiseNode = confirmNoiseNodeId ? nodeById.get(confirmNoiseNodeId)?.api || null : null;

  useEffect(() => {
    if (!actionMenu || !actionNode) return;
    const fallbackActive = transforms.length > 0 && transforms.every((item) => item.source_category === "fallback");
    const key = `${actionMenu.nodeId}:${actionMenu.mode}:${actionTransforms.length}:${transforms.length}:${fallbackActive}`;
    if (lastTransformMenuLogRef.current === key) return;
    lastTransformMenuLogRef.current = key;
    onSystemLog?.(`Transform menu opened for node ${actionNode.api.id}/${actionNode.api.type}: ${actionTransforms.length} compatible transforms / registry ${transforms.length} total / fallback ${fallbackActive ? "yes" : "no"}.`);
  }, [actionMenu, actionNode, actionTransforms.length, onSystemLog, transforms]);

  const worldBounds = useMemo(() => {
    const values = Object.values(positions);
    if (!values.length) return { width: 5000, height: 5000 };
    const minX = Math.min(0, ...values.map((item) => item.x));
    const minY = Math.min(0, ...values.map((item) => item.y));
    const maxX = Math.max(1600, ...values.map((item) => item.x + NODE_WIDTH + 260));
    const maxY = Math.max(1000, ...values.map((item) => item.y + NODE_HEIGHT + 210));
    return { width: maxX - minX, height: maxY - minY };
  }, [positions]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (isTypingTarget(event.target)) return;
      if (event.code === "Space") {
        spaceDownRef.current = true;
        event.preventDefault();
        return;
      }
      if (event.key === "Escape") { setActionMenu(null); setConfirmNoiseNodeId(null); return; }
      if (event.key === "Enter" && selectedId) { event.preventDefault(); setActionMenu({ nodeId: selectedId, mode: "full" }); return; }
      if (event.key === "Delete" && selectedId) { event.preventDefault(); setConfirmNoiseNodeId(selectedId); }
    };
    const onKeyUp = (event: KeyboardEvent) => {
      if (event.code === "Space") spaceDownRef.current = false;
    };
    window.addEventListener("keydown", onKeyDown);
    window.addEventListener("keyup", onKeyUp);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      window.removeEventListener("keyup", onKeyUp);
    };
  }, [selectedId]);

  useEffect(() => {
    const openNodeMenu = (event: Event) => {
      const detail = (event as CustomEvent<{ node_id?: string }>).detail || {};
      const nodeId = detail.node_id || selectedId;
      if (nodeId && nodeById.has(nodeId)) setActionMenu({ nodeId, mode: "full" });
    };
    window.addEventListener("nexus:open-node-transform-menu", openNodeMenu);
    return () => window.removeEventListener("nexus:open-node-transform-menu", openNodeMenu);
  }, [nodeById, selectedId]);

  const beginNodeDrag = (event: ReactPointerEvent<HTMLButtonElement>, node: ApiGraphNode, position: ViewportPoint) => {
    if (event.button !== 0) return;
    event.stopPropagation();
    const world = screenToWorldPoint(event.clientX, event.clientY);
    const target = event.currentTarget;
    try { target.setPointerCapture(event.pointerId); } catch { /* ignored */ }
    interactionRef.current = { type: "node", pointerId: event.pointerId, target, nodeId: node.id, offsetX: world.x - position.x, offsetY: world.y - position.y, startClientX: event.clientX, startClientY: event.clientY, hasDragged: false };
    setDraggingNodeId(node.id);
  };

  const beginPan = (event: ReactPointerEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement | null;
    if (target?.closest(".studio-node,.studio-node-action-menu,.studio-confirm-popover,.graph-floating-controls,.graph-mini-stats")) return;
    if (!(event.button === 0 || event.button === 1 || spaceDownRef.current)) return;
    event.preventDefault();
    setActionMenu(null);
    setConfirmNoiseNodeId(null);
    const element = event.currentTarget;
    try { element.setPointerCapture(event.pointerId); } catch { /* ignored */ }
    interactionRef.current = { type: "pan", pointerId: event.pointerId, target: element, startClientX: event.clientX, startClientY: event.clientY, startPan: panRef.current, hasDragged: false };
    setPanning(true);
  };

  const handleWheel = (event: ReactWheelEvent<HTMLDivElement>) => {
    event.preventDefault();
    const speed = event.ctrlKey || event.metaKey ? 0.0008 : 0.0016;
    const factor = clamp(Math.exp(-event.deltaY * speed), 0.82, 1.18);
    zoomAt(event.clientX, event.clientY, zoomRef.current * factor);
  };

  if (!visibleNodes.length) {
    return (
      <div className="studio-graph-canvas osint-grid" ref={stageRef}>
        <div className="studio-empty-launch">
          <span className="studio-empty-kicker">NEXUSINTEL LINK ANALYSIS</span>
          <h2>Start a Link Analysis</h2>
          <p>Add a seed entity, run a lookup, or import evidence.</p>
          <div className="studio-empty-actions">
            <button type="button" onClick={() => onOpenAddEntity?.("username")}>Add Username</button>
            <button type="button" onClick={() => onOpenAddEntity?.("email")}>Add Email</button>
            <button type="button" onClick={() => onOpenAddEntity?.("domain")}>Add Domain</button>
            <button type="button" onClick={() => onOpenAddEntity?.("phone")}>Add Phone</button>
            <button type="button" onClick={() => onOpenImport?.()}>Import CSV/JSON</button>
            <button type="button" onClick={() => onOpenAddEntity?.()}>Open Entity Palette</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div
      ref={stageRef}
      className={panning ? "studio-graph-canvas osint-grid is-panning" : "studio-graph-canvas osint-grid"}
      onPointerDown={beginPan}
      onWheel={handleWheel}
      onContextMenu={(event) => {
        if ((event.target as HTMLElement | null)?.closest(".studio-node")) return;
        event.preventDefault();
      }}
    >
      <div className="studio-graph-world" style={{ width: worldBounds.width, height: worldBounds.height, transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}>
        <svg className="studio-edge-layer" width={worldBounds.width} height={worldBounds.height}>
          <defs>
            <marker id="nexus-arrow" viewBox="0 0 10 10" refX="18" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 1 L 10 5 L 0 9 z" fill="#2d3748" /></marker>
            <marker id="nexus-arrow-active" viewBox="0 0 10 10" refX="18" refY="5" markerWidth="6.5" markerHeight="6.5" orient="auto-start-reverse"><path d="M 0 1 L 10 5 L 0 9 z" fill="#3b82f6" /></marker>
          </defs>
          {studioEdges.map(({ api, ui }) => {
            const source = nodeById.get(api.source);
            const target = nodeById.get(api.target);
            if (!source || !target) return null;
            const sourcePosition = positions[source.api.id] || { x: 0, y: 0 };
            const targetPosition = positions[target.api.id] || { x: 0, y: 0 };
            const sx = sourcePosition.x + NODE_WIDTH / 2;
            const sy = sourcePosition.y + 32;
            const tx = targetPosition.x + NODE_WIDTH / 2;
            const ty = targetPosition.y + 32;
            const midX = (sx + tx) / 2;
            const midY = (sy + ty) / 2;
            const active = hoveredEdgeId === api.id || Boolean(selectedId && (api.source === selectedId || api.target === selectedId));
            const label = upperSnake(ui.label || api.type);
            return (
              <g key={api.id} onMouseEnter={() => setHoveredEdgeId(api.id)} onMouseLeave={() => setHoveredEdgeId(null)} className={active ? "studio-edge active" : "studio-edge"}>
                <line className="edge-hit" x1={sx} y1={sy} x2={tx} y2={ty} stroke="transparent" strokeWidth="12" />
                {active && <line className="edge-glow" x1={sx} y1={sy} x2={tx} y2={ty} stroke="#3b82f6" strokeWidth="6" />}
                <line className="edge-line" x1={sx} y1={sy} x2={tx} y2={ty} markerEnd={active ? "url(#nexus-arrow-active)" : "url(#nexus-arrow)"} style={{ opacity: Math.max(0.2, ui.confidence / 115) }} />
                {(zoom >= 0.7 || active) && <g className="edge-label" transform={`translate(${midX}, ${midY})`}><rect x={-(label.length * 2.8) - 4} y={-7} width={label.length * 5.6 + 8} height={14} rx="3" /><text textAnchor="middle" y="2.5">{label}</text></g>}
              </g>
            );
          })}
        </svg>
        <div className="studio-node-layer">
          {studioNodes.map(({ api, ui }) => {
            const position = positions[api.id] || { x: 0, y: 0 };
            const visual = getStudioNodeVisual(api.type);
            const selected = selectedId === api.id || multiSelectedIds.has(api.id);
            const hovered = hoveredNodeId === api.id;
            const confidence = getStudioNodeConfidence(api);
            const source = nodeSource(api);
            const icon = NODE_ICON_PATHS[getStudioNodeIcon(api.type)] || NODE_ICON_PATHS.target;
            const risk = getStudioNodeRisk(api);
            return (
              <button
                type="button"
                key={api.id}
                className={`studio-node family-${visual.family} ${selected ? "selected" : ""} ${hovered ? "hovered" : ""} ${draggingNodeId === api.id ? "dragging" : ""}`}
                style={{ "--node-accent": visual.accent, transform: `translate(${position.x}px, ${position.y}px)` } as CSSProperties}
                onPointerDown={(event) => beginNodeDrag(event, api, position)}
                onMouseEnter={() => setHoveredNodeId(api.id)}
                onMouseLeave={() => setHoveredNodeId(null)}
                onClick={(event) => {
                  event.stopPropagation();
                  if (suppressClickNodeRef.current === api.id) {
                    suppressClickNodeRef.current = null;
                    event.preventDefault();
                    return;
                  }
                  if (event.ctrlKey || event.metaKey || event.shiftKey) {
                    setMultiSelectedIds((current) => {
                      const next = new Set(current);
                      if (next.has(api.id)) next.delete(api.id); else next.add(api.id);
                      return next;
                    });
                  }
                  onSelectNode(api);
                  setDataPanelOpen?.(true);
                  setActionMenu({ nodeId: api.id, mode: "compact" });
                }}
                onContextMenu={(event) => {
                  event.preventDefault();
                  event.stopPropagation();
                  onSelectNode(api);
                  setDataPanelOpen?.(true);
                  setActionMenu({ nodeId: api.id, mode: "full" });
                }}
                onDoubleClick={(event) => {
                  event.stopPropagation();
                  onSelectNode(api);
                  setDataPanelOpen?.(true);
                  setActionMenu({ nodeId: api.id, mode: "full" });
                }}
              >
                <span className="studio-node-bubble">
                  <svg viewBox="0 0 64 64" aria-hidden="true"><g fill="none" stroke="currentColor" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{ __html: icon }} /></svg>
                  <i className="studio-confidence-dot" style={{ background: confidence >= 80 ? "#10B981" : confidence >= 50 ? "#F59E0B" : "#EF4444" }}>{confidence}</i>
                </span>
                <span className="studio-node-card">
                  <span className="studio-node-card-top"><span className="studio-node-type">{visual.code}</span>{risk && <span className="studio-risk-badge">{risk}</span>}</span>
                  <strong>{compactLabel(ui.label || api.label || api.value || api.type)}</strong>
                  <small>{confidence}% / {source}</small>
                </span>
              </button>
            );
          })}
        </div>
      </div>
      {actionNode && menuStyle && (
        <NodeActionPopover
          node={actionNode.api}
          mode={actionMenu?.mode || "compact"}
          style={menuStyle as CSSProperties}
          transforms={actionTransforms}
          loadingId={transformLoading}
          error={transformError}
          onClose={() => setActionMenu(null)}
          onRun={(id, node) => onRunTransform?.(id, node)}
          onOpenInspector={() => setDataPanelOpen?.(true)}
          onOpenEvidence={(node) => onOpenEvidenceVault?.(node)}
          onMarkNoise={(node) => setConfirmNoiseNodeId(node.id)}
          onCorrelate={() => onRunCorrelation?.()}
          onOpenTransformLibrary={() => onOpenTransformLibrary?.()}
          onExpand={() => setActionMenu({ nodeId: actionNode.api.id, mode: "full" })}
        />
      )}
      {confirmNoiseNode && (
        <section className="studio-confirm-popover">
          <strong>Mark entity as noise?</strong>
          <p>{confirmNoiseNode.label || confirmNoiseNode.value || confirmNoiseNode.id} will be removed from the main graph and kept in the noise bin if the backend accepts it.</p>
          <div><button type="button" onClick={() => setConfirmNoiseNodeId(null)}>Cancel</button><button type="button" className="danger" onClick={() => { onMarkNoiseNode?.(confirmNoiseNode); setConfirmNoiseNodeId(null); setActionMenu(null); }}>Mark Noise</button></div>
        </section>
      )}
      {hoveredNodeId && nodeById.has(hoveredNodeId) && (
        <div className="studio-hover-card">
          <strong>{nodeById.get(hoveredNodeId)?.ui.label}</strong>
          <span>{nodeById.get(hoveredNodeId)?.ui.type} / {nodeById.get(hoveredNodeId)?.ui.confidence}% confidence</span>
          <small>{nodeById.get(hoveredNodeId)?.ui.source}</small>
        </div>
      )}
      <div className="graph-mini-stats"><span>E <strong>{visibleNodes.length}</strong></span><span>R <strong>{visibleEdges.length}</strong></span><span>{layoutMode}</span><span>Sel <strong>{Math.max(multiSelectedIds.size, selectedId ? 1 : 0)}</strong></span></div>
      <div className="graph-enterprise-tools">
        <button type="button" onClick={() => {
          if (!selectedId) return;
          const neighbors = new Set<string>([selectedId]);
          visibleEdges.forEach((edge) => { if (edge.source === selectedId) neighbors.add(edge.target); if (edge.target === selectedId) neighbors.add(edge.source); });
          setMultiSelectedIds(neighbors);
          onSystemLog?.(`Selected ${neighbors.size} neighbor node(s).`);
        }}>Select Neighbors</button>
        <button type="button" onClick={() => {
          const ids = new Set(multiSelectedIds.size ? multiSelectedIds : selectedId ? [selectedId] : []);
          setHiddenNodeIds((current) => new Set([...current, ...ids]));
          setActionMenu(null);
        }}>Hide Selected</button>
        <button type="button" onClick={() => { setHiddenNodeIds(new Set()); setMultiSelectedIds(new Set()); }}>Show All</button>
        <label><input type="checkbox" checked={showCandidates} onChange={(event) => setShowCandidates(event.target.checked)} />Candidates</label>
        <label><input type="checkbox" checked={showSignals} onChange={(event) => setShowSignals(event.target.checked)} />Signals</label>
        <label>Confidence<input type="range" min="0" max="90" step="10" value={minConfidence} onChange={(event) => setMinConfidence(Number(event.target.value))} /></label>
      </div>
      <div className="graph-minimap" aria-label="Graph minimap">
        {visibleNodes.slice(0, 160).map((node, index) => {
          const pos = positions[node.id] || positionFor(index, visibleNodes.length, 1240, 760, layoutMode);
          return <i key={node.id} className={selectedId === node.id || multiSelectedIds.has(node.id) ? "active" : ""} style={{ left: `${clamp((pos.x / Math.max(1, worldBounds.width)) * 100, 1, 96)}%`, top: `${clamp((pos.y / Math.max(1, worldBounds.height)) * 100, 1, 92)}%` }} />;
        })}
      </div>
      <div className="graph-floating-controls">
        <button type="button" onClick={() => zoomAtCenter(1.12)} title="Zoom in"><ZoomIn size={15} /></button>
        <button type="button" onClick={() => zoomAtCenter(0.88)} title="Zoom out"><ZoomOut size={15} /></button>
        <button type="button" onClick={fitGraph} title="Fit graph"><Maximize2 size={15} /></button>
        <button type="button" onClick={resetZoom} title="Reset zoom"><RotateCcw size={15} /><span>{Math.round(zoom * 100)}%</span></button>
      </div>
    </div>
  );
}
