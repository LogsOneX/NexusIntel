import { type CSSProperties, type Dispatch, type FormEvent, type SetStateAction, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Maximize2, RotateCcw, ZoomIn, ZoomOut } from "lucide-react";
import { mapApiEdgeToStudioEdge, mapApiNodeToStudioNode } from "../lib/studioMappers";
import NodeActionPopover from "../components/graph/NodeActionPopover";
import type { TransformDefinition } from "../lib/types";

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

type LayoutMode = "tree" | "circular" | "force";
type StudioPosition = { x: number; y: number };

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

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

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

type NodeVisual = { accent: string; code: string; icon: string; family: string };

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
  star: `<path d="M32 10l6 15h16l-13 9 5 16-14-10-14 10 5-16-13-9h16z"/>`,
  lock: `<path d="M16 30h32v22H16z"/><path d="M23 30v-7a9 9 0 0118 0v7"/><path d="M32 39v6"/>`,
  alert: `<path d="M32 9l25 44H7z"/><path d="M32 24v13M32 45h.1"/>`,
  target: `<circle cx="32" cy="32" r="20"/><circle cx="32" cy="32" r="8"/><path d="M32 6v10M32 48v10M6 32h10M48 32h10"/>`,
};

const NODE_VISUALS: Record<string, NodeVisual> = {
  username: { accent: "#3B82F6", code: "USER", icon: "fingerprint", family: "identity" },
  name: { accent: "#3B82F6", code: "ALIAS", icon: "identity", family: "identity" },
  person_alias: { accent: "#3B82F6", code: "ALIAS", icon: "identity", family: "identity" },
  profile: { accent: "#3B82F6", code: "PROF", icon: "fingerprint", family: "identity" },
  account: { accent: "#3B82F6", code: "ACCT", icon: "identity", family: "identity" },
  email: { accent: "#10B981", code: "EMAIL", icon: "mail", family: "contact" },
  masked_email: { accent: "#10B981", code: "MASK", icon: "lock", family: "contact" },
  phone: { accent: "#10B981", code: "PHONE", icon: "phone", family: "contact" },
  domain: { accent: "#A855F7", code: "DNS", icon: "globe", family: "infra" },
  url: { accent: "#A855F7", code: "URL", icon: "link", family: "infra" },
  ip: { accent: "#A855F7", code: "IP", icon: "server", family: "infra" },
  dns_record: { accent: "#A855F7", code: "DNS", icon: "server", family: "infra" },
  certificate: { accent: "#A855F7", code: "CERT", icon: "file", family: "infra" },
  service: { accent: "#A855F7", code: "SVC", icon: "server", family: "infra" },
  technology: { accent: "#A855F7", code: "TECH", icon: "server", family: "infra" },
  google_profile: { accent: "#F59E0B", code: "MAPS", icon: "pin", family: "geo" },
  google_maps_profile: { accent: "#F59E0B", code: "MAPS", icon: "pin", family: "geo" },
  google_review: { accent: "#F59E0B", code: "REVIEW", icon: "star", family: "geo" },
  location: { accent: "#F59E0B", code: "LOC", icon: "pin", family: "geo" },
  place: { accent: "#F59E0B", code: "PLACE", icon: "pin", family: "geo" },
  image_asset: { accent: "#F59E0B", code: "IMG", icon: "image", family: "asset" },
  avatar: { accent: "#F59E0B", code: "IMG", icon: "image", family: "asset" },
  favicon: { accent: "#F59E0B", code: "HASH", icon: "image", family: "asset" },
  hash: { accent: "#F59E0B", code: "HASH", icon: "file", family: "asset" },
  document: { accent: "#8B8B91", code: "DOC", icon: "file", family: "asset" },
  evidence: { accent: "#8B8B91", code: "EV", icon: "file", family: "asset" },
  crypto_wallet: { accent: "#10B981", code: "WALLET", icon: "wallet", family: "crypto" },
  wallet: { accent: "#10B981", code: "WALLET", icon: "wallet", family: "crypto" },
  crypto_transaction: { accent: "#10B981", code: "TX", icon: "transaction", family: "crypto" },
  transaction: { accent: "#10B981", code: "TX", icon: "transaction", family: "crypto" },
  suspicious_domain: { accent: "#EF4444", code: "RISK", icon: "alert", family: "threat" },
  breach_record: { accent: "#EF4444", code: "BREACH", icon: "alert", family: "threat" },
  indicator: { accent: "#EF4444", code: "IOC", icon: "alert", family: "threat" },
  target: { accent: "#EF4444", code: "ROOT", icon: "target", family: "system" },
  investigation_root: { accent: "#EF4444", code: "ROOT", icon: "target", family: "system" },
  note: { accent: "#8B8B91", code: "NOTE", icon: "file", family: "system" },
  signal: { accent: "#8B8B91", code: "SIG", icon: "target", family: "system" },
};

const HIDDEN_NODE_TYPES = new Set([
  "guardrail", "compliance", "skipped_check", "legal_note", "policy", "policy_notice", "blocked_transform", "prohibited_probe_notice",
  "noise", "soft_404", "auth_wall_only", "generic_login_page", "parked_domain", "registrar_privacy_noise",
]);

const CANDIDATE_NODE_TYPES = new Set([
  "profile_candidate", "candidate_profile", "candidate_url_only", "username_candidate", "email_candidate", "phone_deeplink_candidate", "possible_profile", "possible_same_actor",
]);

function visualForNodeType(type: string): NodeVisual {
  const normalized = String(type || "").toLowerCase();
  if (normalized.includes("risk") || normalized.includes("suspicious")) return NODE_VISUALS.suspicious_domain;
  if (normalized.includes("candidate") || normalized.includes("possible")) return { accent: "#F59E0B", code: "LEAD", icon: "target", family: "candidate" };
  return NODE_VISUALS[normalized] || NODE_VISUALS.profile;
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
    return `${local.slice(0, 12)}…@${(domain || "").slice(0, 12)}`;
  }
  return `${clean.slice(0, 25)}…`;
}

function nodeConfidence(node: ApiGraphNode): number {
  const data = node.data || {};
  const numeric = Number(node.confidence_level ?? data.confidence_score ?? data.confidence_level);
  if (Number.isFinite(numeric)) return Math.max(0, Math.min(100, numeric));
  return confidenceScore(node.confidence) || 50;
}

function nodeSource(node: ApiGraphNode): string {
  return String(node.source || node.data?.source || node.data?.adapter_id || "graph");
}

function isPrivateOrBogonIp(value: string): boolean {
  const ip = value.trim().toLowerCase();
  return /^(10|127|0)\./.test(ip) || /^192\.168\./.test(ip) || /^172\.(1[6-9]|2\d|3[01])\./.test(ip) || /^169\.254\./.test(ip) || /^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\./.test(ip) || ip === "::1" || ip.startsWith("fc") || ip.startsWith("fd") || ip.startsWith("fe80:");
}

function suspiciousDomain(value: string): boolean {
  const domain = value.toLowerCase();
  return ["login-", "secure-", "verify-", "account-", "wallet-", "signin-", "-login", "-verify", "password", "update-billing"].some((term) => domain.includes(term));
}

function nodeRiskTag(node: ApiGraphNode): "INTERNAL" | "SUSPICIOUS" | null {
  const value = String(node.value || node.label || "");
  if (node.type === "ip" && isPrivateOrBogonIp(value)) return "INTERNAL";
  if (node.type === "domain" && suspiciousDomain(value)) return "SUSPICIOUS";
  return null;
}

function positionFor(index: number, total: number, width: number, height: number, mode: LayoutMode): StudioPosition {
  const centerX = Math.max(440, width / 2);
  const centerY = Math.max(280, height / 2);
  if (mode === "tree") {
    const columns = Math.max(1, Math.ceil(Math.sqrt(total || 1)));
    return { x: 155 + (index % columns) * 190, y: 118 + Math.floor(index / columns) * 150 };
  }
  if (mode === "circular") {
    const radius = Math.max(190, Math.min(width, height) * 0.32);
    const angle = total <= 1 ? -Math.PI / 2 : (index / total) * Math.PI * 2 - Math.PI / 2;
    return { x: centerX + Math.cos(angle) * radius - 66, y: centerY + Math.sin(angle) * radius - 38 };
  }
  const radius = 92 + Math.sqrt(index + 1) * 58;
  const angle = index * GOLDEN_ANGLE;
  return { x: centerX + Math.cos(angle) * radius - 66, y: centerY + Math.sin(angle) * radius - 38 };
}

function graphNodeForReport(node: ApiGraphNode, position: StudioPosition): GraphNode {
  return {
    id: node.id,
    nodeType: node.type,
    nodeLabel: node.label || node.value || node.type,
    nodeProperties: { ...(node.data || {}), value: node.value, source: node.source || "graph", confidence: node.confidence || "medium", confidence_level: nodeConfidence(node), created_at: node.created_at || new Date().toISOString() },
    nodeShape: "circle",
    x: position.x,
    y: position.y,
    nodeIcon: null,
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

export default function GraphCanvas({
  investigationId,
  nodes,
  edges,
  selectedNode,
  onSelectNode,
  onSystemLog,
  onOracleNode,
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
  const [positions, setPositions] = useState<Record<string, StudioPosition>>({});
  const [layoutMode, setLayoutMode] = useState<LayoutMode>("force");
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState<{ id: string; offsetX: number; offsetY: number } | null>(null);
  const [panning, setPanning] = useState<{ x: number; y: number; startX: number; startY: number } | null>(null);
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null);
  const [actionMenu, setActionMenu] = useState<{ nodeId: string; mode: "compact" | "full" } | null>(null);
  const [confirmNoiseNodeId, setConfirmNoiseNodeId] = useState<string | null>(null);

  const visibleNodes = useMemo(() => nodes.filter(isGraphVisible), [nodes]);
  const visibleNodeIds = useMemo(() => new Set(visibleNodes.map((node) => node.id)), [visibleNodes]);
  const visibleEdges = useMemo(() => edges.filter((edge) => visibleNodeIds.has(edge.source) && visibleNodeIds.has(edge.target)), [edges, visibleNodeIds]);
  const studioNodes = useMemo(() => visibleNodes.map((node, index) => ({ api: node, ui: mapApiNodeToStudioNode(node, index) })), [visibleNodes]);
  const studioEdges = useMemo(() => visibleEdges.map((edge, index) => ({ api: edge, ui: mapApiEdgeToStudioEdge(edge, index) })), [visibleEdges]);
  const selectedId = selectedNode?.id || null;

  const applyLayout = useCallback((mode: LayoutMode = layoutMode) => {
    const rect = stageRef.current?.getBoundingClientRect();
    const width = rect?.width || 1240;
    const height = rect?.height || 760;
    setLayoutMode(mode);
    setPositions(Object.fromEntries(visibleNodes.map((node, index) => [node.id, positionFor(index, visibleNodes.length, width, height, mode)])));
    onSystemLog?.(`Graph layout switched to ${mode}.`);
  }, [layoutMode, onSystemLog, visibleNodes]);

  useEffect(() => {
    setPositions((current) => {
      const rect = stageRef.current?.getBoundingClientRect();
      const width = rect?.width || 1240;
      const height = rect?.height || 760;
      let changed = false;
      const next = { ...current };
      visibleNodes.forEach((node, index) => {
        if (!next[node.id]) {
          const dataX = Number(node.data?.x);
          const dataY = Number(node.data?.y);
          next[node.id] = Number.isFinite(dataX) && Number.isFinite(dataY) ? { x: dataX, y: dataY } : positionFor(index, visibleNodes.length, width, height, layoutMode);
          changed = true;
        }
      });
      Object.keys(next).forEach((id) => {
        if (!visibleNodeIds.has(id)) {
          delete next[id];
          changed = true;
        }
      });
      return changed ? next : current;
    });
  }, [layoutMode, visibleNodeIds, visibleNodes]);

  const fitGraph = useCallback(() => {
    setZoom(1);
    setPan({ x: 0, y: 0 });
    onSystemLog?.("Graph viewport fitted.");
  }, [onSystemLog]);

  const exportGraph = useCallback(() => {
    const reportNodes = visibleNodes.map((node, index) => graphNodeForReport(node, positions[node.id] || positionFor(index, visibleNodes.length, 1240, 760, layoutMode)));
    const reportEdges = visibleEdges.map(graphEdgeForReport);
    const blob = new Blob([reportHtml(reportNodes, reportEdges, investigationId)], { type: "text/html;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `nexusintel-graph-${investigationId || "local"}.html`;
    link.click();
    URL.revokeObjectURL(url);
    onSystemLog?.("Graph report exported from Studio renderer.");
  }, [investigationId, layoutMode, onSystemLog, positions, visibleEdges, visibleNodes]);

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
    const onMove = (event: MouseEvent) => {
      if (dragging) {
        setPositions((current) => ({
          ...current,
          [dragging.id]: { x: (event.clientX - pan.x) / zoom - dragging.offsetX, y: (event.clientY - pan.y) / zoom - dragging.offsetY },
        }));
        return;
      }
      if (panning) setPan({ x: panning.x + event.clientX - panning.startX, y: panning.y + event.clientY - panning.startY });
    };
    const onUp = () => {
      setDragging(null);
      setPanning(null);
    };
    window.addEventListener("mousemove", onMove);
    window.addEventListener("mouseup", onUp);
    return () => {
      window.removeEventListener("mousemove", onMove);
      window.removeEventListener("mouseup", onUp);
    };
  }, [dragging, pan.x, pan.y, panning, zoom]);

  const nodeById = useMemo(() => new Map(studioNodes.map((node) => [node.api.id, node])), [studioNodes]);
  const actionNode = actionMenu ? nodeById.get(actionMenu.nodeId) || null : null;
  const actionTransforms = useMemo(() => {
    if (!actionNode) return [] as TransformDefinition[];
    return transforms.filter((item) => item.input_types.includes(actionNode.api.type) || item.input_types.includes("*"));
  }, [actionNode, transforms]);
  const recommendedTransform = actionTransforms.find((item) => item.enabled) || null;
  const actionPosition = actionNode ? positions[actionNode.api.id] : null;
  const menuStyle = actionPosition ? {
    left: Math.max(16, Math.min((stageRef.current?.clientWidth || 1200) - 360, pan.x + (actionPosition.x + 138) * zoom + 12)),
    top: Math.max(12, Math.min((stageRef.current?.clientHeight || 760) - 390, pan.y + actionPosition.y * zoom + 4)),
  } : undefined;
  const confirmNoiseNode = confirmNoiseNodeId ? nodeById.get(confirmNoiseNodeId)?.api || null : null;
  const worldBounds = useMemo(() => {
    const values = Object.values(positions);
    if (!values.length) return { width: 1600, height: 1000 };
    return { width: Math.max(1600, Math.max(...values.map((item) => item.x)) + 260), height: Math.max(1000, Math.max(...values.map((item) => item.y)) + 210) };
  }, [positions]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      const target = event.target as HTMLElement | null;
      const typing = target?.tagName === "INPUT" || target?.tagName === "TEXTAREA" || target?.tagName === "SELECT" || target?.isContentEditable;
      if (typing) return;
      if (event.key === "Escape") { setActionMenu(null); setConfirmNoiseNodeId(null); return; }
      if (event.key === "Enter" && selectedId) { event.preventDefault(); setActionMenu({ nodeId: selectedId, mode: "full" }); return; }
      if (event.key === "Delete" && selectedId) { event.preventDefault(); setConfirmNoiseNodeId(selectedId); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
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

  if (!visibleNodes.length) {
    return (
      <div className="studio-graph-canvas osint-grid">
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
      className="studio-graph-canvas osint-grid"
      onMouseDown={(event) => {
        if (event.button === 0 && event.target === event.currentTarget) setPanning({ x: pan.x, y: pan.y, startX: event.clientX, startY: event.clientY });
      }}
      onWheel={(event) => {
        event.preventDefault();
        setZoom((current) => Math.max(0.45, Math.min(1.7, current + (event.deltaY > 0 ? -0.08 : 0.08))));
      }}
    >
      <div className="studio-graph-world" style={{ width: worldBounds.width, height: worldBounds.height, transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}>
        <svg className="studio-edge-layer" width={worldBounds.width} height={worldBounds.height}>
          {studioEdges.map(({ api, ui }) => {
            const source = nodeById.get(api.source);
            const target = nodeById.get(api.target);
            if (!source || !target) return null;
            const sourcePosition = positions[source.api.id] || { x: 0, y: 0 };
            const targetPosition = positions[target.api.id] || { x: 0, y: 0 };
            const sx = sourcePosition.x + 66;
            const sy = sourcePosition.y + 35;
            const tx = targetPosition.x + 66;
            const ty = targetPosition.y + 35;
            const dx = tx - sx;
            const path = `M ${sx} ${sy} C ${sx + dx * 0.36} ${sy}, ${tx - dx * 0.36} ${ty}, ${tx} ${ty}`;
            const midX = (sx + tx) / 2;
            const midY = (sy + ty) / 2;
            const active = hoveredEdgeId === api.id || Boolean(selectedId && (api.source === selectedId || api.target === selectedId));
            return (
              <g key={api.id} onMouseEnter={() => setHoveredEdgeId(api.id)} onMouseLeave={() => setHoveredEdgeId(null)} className={active ? "studio-edge active" : "studio-edge"}>
                <path d={path} style={{ opacity: Math.max(0.18, ui.confidence / 115) }} />
                <text x={midX} y={midY - 8}>{upperSnake(ui.label || api.type)}</text>
              </g>
            );
          })}
        </svg>
        <div className="studio-node-layer">
          {studioNodes.map(({ api, ui }) => {
            const position = positions[api.id] || { x: 0, y: 0 };
            const visual = visualForNodeType(api.type);
            const selected = selectedId === api.id;
            const hovered = hoveredNodeId === api.id;
            const confidence = nodeConfidence(api);
            const source = nodeSource(api);
            const icon = NODE_ICON_PATHS[visual.icon] || NODE_ICON_PATHS.target;
            const risk = nodeRiskTag(api);
            return (
              <button
                type="button"
                key={api.id}
                className={`studio-node family-${visual.family} ${selected ? "selected" : ""} ${hovered ? "hovered" : ""}`}
                style={{ "--node-accent": visual.accent, transform: `translate(${position.x}px, ${position.y}px)` } as CSSProperties}
                onMouseDown={(event) => {
                  event.stopPropagation();
                  setDragging({ id: api.id, offsetX: (event.clientX - pan.x) / zoom - position.x, offsetY: (event.clientY - pan.y) / zoom - position.y });
                }}
                onMouseEnter={() => setHoveredNodeId(api.id)}
                onMouseLeave={() => setHoveredNodeId(null)}
                onClick={(event) => {
                  event.stopPropagation();
                  onSelectNode(api);
                  setDataPanelOpen?.(true);
                  setActionMenu({ nodeId: api.id, mode: "compact" });
                }}
                onContextMenu={(event) => {
                  event.preventDefault();
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
                  <i className="studio-confidence-dot" style={{ background: confidence >= 80 ? "#10B981" : confidence >= 50 ? "#F59E0B" : "#EF4444" }} />
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
      <div className="graph-mini-stats"><span>E <strong>{visibleNodes.length}</strong></span><span>R <strong>{visibleEdges.length}</strong></span><span>{layoutMode}</span></div>
      <div className="graph-floating-controls">
        <button type="button" onClick={() => setZoom((value) => Math.min(1.7, value + 0.1))} title="Zoom in"><ZoomIn size={15} /></button>
        <button type="button" onClick={() => setZoom((value) => Math.max(0.45, value - 0.1))} title="Zoom out"><ZoomOut size={15} /></button>
        <button type="button" onClick={fitGraph} title="Fit graph"><Maximize2 size={15} /></button>
        <button type="button" onClick={() => applyLayout(layoutMode)} title="Reflow layout"><RotateCcw size={15} /></button>
      </div>
    </div>
  );
}
