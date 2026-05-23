import { type CSSProperties, type Dispatch, type FormEvent, type SetStateAction, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
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
};

const API_BASE = import.meta.env.VITE_API_BASE || "";
const PALETTE_TYPES = ["username", "email", "domain", "ip", "phone", "crypto_wallet"] as const;
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
  if (["domain", "platform", "service", "dns_record", "location"].includes(type)) return "hexagon";
  if (["crypto_wallet", "crypto_transaction", "transaction"].includes(type)) return "square";
  if (["ip", "profile", "avatar_hash", "signal", "google_review", "google_profile", "censored_email", "censored_phone"].includes(type)) return "square";
  if (["phone", "guardrail", "breach", "risk"].includes(type)) return "triangle";
  return "circle";
}

function cyShape(shape: GraphNode["nodeShape"]): string {
  if (shape === "circle") return "ellipse";
  if (shape === "square") return "rectangle";
  if (shape === "triangle") return "triangle";
  return "hexagon";
}

function svgDataUri(svg: string): string {
  const cleanSvg = svg
    .replace(/<rect width="64" height="64" fill="#111111"\/>/g, "")
    .replace(/stroke-width="4"/g, 'stroke-width="5"');
  return `data:image/svg+xml;utf8,${encodeURIComponent(cleanSvg)}`;
}

const CY_NODE_ICONS: Record<string, string> = {
  username: svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#111111"/><circle cx="32" cy="22" r="10" fill="none" stroke="#ffffff" stroke-width="4"/><path d="M14 54c3-13 11-20 18-20s15 7 18 20" fill="none" stroke="#ffffff" stroke-width="4" stroke-linecap="square"/></svg>`),
  name: svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#111111"/><circle cx="32" cy="22" r="10" fill="none" stroke="#ffffff" stroke-width="4"/><path d="M14 54c3-13 11-20 18-20s15 7 18 20" fill="none" stroke="#ffffff" stroke-width="4" stroke-linecap="square"/></svg>`),
  email: svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#111111"/><rect x="10" y="18" width="44" height="30" fill="none" stroke="#ffffff" stroke-width="4"/><path d="M12 20l20 17 20-17" fill="none" stroke="#ffffff" stroke-width="4" stroke-linecap="square"/></svg>`),
  domain: svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#111111"/><circle cx="32" cy="32" r="22" fill="none" stroke="#ffffff" stroke-width="4"/><path d="M10 32h44M32 10c8 8 8 36 0 44M32 10c-8 8-8 36 0 44" fill="none" stroke="#ffffff" stroke-width="3"/></svg>`),
  ip: svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#111111"/><rect x="12" y="14" width="40" height="12" fill="none" stroke="#ffffff" stroke-width="4"/><rect x="12" y="30" width="40" height="12" fill="none" stroke="#ffffff" stroke-width="4"/><rect x="12" y="46" width="40" height="6" fill="none" stroke="#ffffff" stroke-width="4"/><path d="M20 20h4M20 36h4" stroke="#ffffff" stroke-width="4"/></svg>`),
  phone: svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#111111"/><path d="M22 10h20v44H22z" fill="none" stroke="#ffffff" stroke-width="4"/><path d="M29 47h6" stroke="#ffffff" stroke-width="4"/></svg>`),
  crypto_wallet: svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#111111"/><path d="M10 20h44v30H10z" fill="none" stroke="#ffffff" stroke-width="4"/><path d="M44 30h12v12H44z" fill="none" stroke="#ffffff" stroke-width="4"/><path d="M22 42V18h24" fill="none" stroke="#ffffff" stroke-width="4"/></svg>`),
  crypto_transaction: svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#111111"/><path d="M12 22h34l-8-8M46 22l-8 8" fill="none" stroke="#ffffff" stroke-width="4"/><path d="M52 42H18l8-8M18 42l8 8" fill="none" stroke="#ffffff" stroke-width="4"/></svg>`),
  transaction: svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#111111"/><path d="M12 22h34l-8-8M46 22l-8 8" fill="none" stroke="#ffffff" stroke-width="4"/><path d="M52 42H18l8-8M18 42l8 8" fill="none" stroke="#ffffff" stroke-width="4"/></svg>`),
  censored_email: svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#111111"/><path d="M16 30h32v22H16z" fill="none" stroke="#ffffff" stroke-width="4"/><path d="M23 30v-7a9 9 0 0118 0v7" fill="none" stroke="#ffffff" stroke-width="4"/><path d="M32 39v6" stroke="#ffffff" stroke-width="4"/></svg>`),
  censored_phone: svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#111111"/><path d="M16 30h32v22H16z" fill="none" stroke="#ffffff" stroke-width="4"/><path d="M23 30v-7a9 9 0 0118 0v7" fill="none" stroke="#ffffff" stroke-width="4"/><path d="M32 39v6" stroke="#ffffff" stroke-width="4"/></svg>`),
  google_review: svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#111111"/><path d="M32 10l6 15h16l-13 9 5 16-14-10-14 10 5-16-13-9h16z" fill="none" stroke="#ffffff" stroke-width="4" stroke-linejoin="miter"/></svg>`),
  location: svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#111111"/><path d="M32 56s18-18 18-32A18 18 0 1014 24c0 14 18 32 18 32z" fill="none" stroke="#ffffff" stroke-width="4"/><circle cx="32" cy="24" r="6" fill="none" stroke="#ffffff" stroke-width="4"/></svg>`),
  profile: svgDataUri(`<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#111111"/><path d="M32 10l20 12v20L32 54 12 42V22z" fill="none" stroke="#ffffff" stroke-width="4"/><path d="M24 32h16" stroke="#ffffff" stroke-width="4"/></svg>`),
};

function iconForNodeType(type: string): string {
  return CY_NODE_ICONS[type] || CY_NODE_ICONS.profile;
}

function displayTypeLabel(type: string): string {
  if (type === "google_review") return "[REVIEW]";
  if (type === "location") return "[LOCATION]";
  return `[${upperSnake(type)}]`;
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
    confidence_level: typeof node.nodeProperties.confidence_level === "number" ? node.nodeProperties.confidence_level : confidenceScore(String(node.nodeProperties.confidence || "medium")),
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
        confidence_level: typeof node.confidence_level === "number" ? node.confidence_level : typeof node.data?.confidence_level === "number" ? node.data.confidence_level : previous.nodeProperties.confidence_level,
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
      confidence_level: typeof node.confidence_level === "number" ? node.confidence_level : typeof node.data?.confidence_level === "number" ? node.data.confidence_level : confidenceScore(node.confidence),
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
    created_at: edge.created_at || String(edge.data?.created_at || ""),
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
  if (["username", "name", "profile", "profile_candidate"].includes(node.nodeType)) {
    return [
      { id: "username_to_email", label: "Username -> Email", description: "Generate mailbox candidates and public email pivots from this handle" },
      { id: "username_identity_sweep", label: "Username Identity Sweep", description: "Resolve confirmed public account/profile surfaces" },
      { id: "tier_1_major_socials", label: "Major Socials", description: "Facebook, Instagram, LinkedIn, X, Threads, TikTok" },
      { id: "tier_2_tech_dev", label: "Tech & Dev", description: "GitHub, GitLab, StackOverflow, HackTheBox" },
      { id: "tier_3_gaming_forums", label: "Gaming & Forums", description: "Steam, Discord, Reddit, Twitch" },
      { id: "tier_4_deep_sweep", label: "Deep Sweep", description: "Full 100+ site Maigret/Sherlock execution" },
    ];
  }
  if (node.nodeType === "email") {
    return [
      { id: "check_email_registrations", label: "Check Registrations", description: "Analyze public registration response signatures without stripping the domain" },
      { id: "google_footprint_lookup", label: "Google Footprint", description: "Verified public Maps profile URL review expansion only" },
      { id: "email_to_domain", label: "Email -> Domain", description: "Extract mail domain, MX, DMARC, SPF, BIMI and DNS records" },
    ];
  }
  if (node.nodeType === "crypto_wallet") {
    return [
      { id: "check_wallet_balance", label: "Check Balance", description: "Fetch public chain balance and wallet summary" },
      { id: "trace_transactions", label: "Trace Transactions", description: "Create linked transaction nodes and public flow edges" },
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
      { id: "phone_to_email", label: "Phone -> Email", description: "Create conservative public contact/email pivot candidates from numbering metadata" },
      { id: "check_messenger_presence", label: "Messenger Presence", description: "Validate E.164 and parse public deep-link metadata only" },
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

function confidenceLevelForNode(node: GraphNode): number {
  const numeric = Number(node.nodeProperties.confidence_level);
  if (Number.isFinite(numeric)) return numeric;
  return confidenceScore(String(node.nodeProperties.confidence || "medium")) || 50;
}

function timestampForNode(node: GraphNode): number {
  const raw = String(node.nodeProperties.created_at || node.nodeProperties.timestamp || "");
  const parsed = Date.parse(raw);
  return Number.isFinite(parsed) ? parsed : 0;
}

function timestampForEdge(edge: GraphEdge): number {
  const parsed = Date.parse(String(edge.created_at || ""));
  return Number.isFinite(parsed) ? parsed : 0;
}

function isPrivateOrBogonIp(value: string): boolean {
  const ip = value.trim().toLowerCase();
  return /^(10|127|0)\./.test(ip) || /^192\.168\./.test(ip) || /^172\.(1[6-9]|2\d|3[01])\./.test(ip) || /^169\.254\./.test(ip) || /^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\./.test(ip) || ip === "::1" || ip.startsWith("fc") || ip.startsWith("fd") || ip.startsWith("fe80:");
}

function suspiciousDomain(value: string): boolean {
  const domain = value.toLowerCase();
  return ["login-", "secure-", "verify-", "account-", "wallet-", "signin-", "-login", "-verify", "password", "update-billing"].some((term) => domain.includes(term));
}

function passiveNodeTag(node: GraphNode): "INTERNAL" | "SUSPICIOUS" | null {
  const value = String(node.nodeProperties.value || node.nodeLabel);
  if (node.nodeType === "ip" && isPrivateOrBogonIp(value)) return "INTERNAL";
  if (node.nodeType === "domain" && suspiciousDomain(value)) return "SUSPICIOUS";
  return null;
}

function nodeElement(node: GraphNode): cytoscape.ElementDefinition {
  const confidence = String(node.nodeProperties.confidence || "medium");
  const tag = passiveNodeTag(node);
  return {
    group: "nodes",
    data: {
      id: node.id,
      label: `${tag ? `[${tag}] ` : ""}${node.nodeLabel}
[${upperSnake(node.nodeType)}]`,
      rawLabel: node.nodeLabel,
      tag: tag || "",
      nodeType: node.nodeType,
      typeLabel: displayTypeLabel(node.nodeType),
      value: String(node.nodeProperties.value || node.nodeLabel),
      icon: iconForNodeType(node.nodeType),
      confidence,
      nodeShape: cyShape(node.nodeShape),
      flag: node.nodeFlag || "",
    },
    position: { x: node.x, y: node.y },
    classes: `entity shape-${node.nodeShape} ${confidence === "low" ? "low-confidence" : ""} ${node.nodeType.startsWith("censored_") ? "censored-entity" : ""} ${node.nodeType === "location" ? "location-entity" : ""} ${tag === "INTERNAL" ? "tag-internal" : ""} ${tag === "SUSPICIOUS" ? "tag-suspicious" : ""}`,
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
      created_at: edge.created_at || "",
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
  onAddSeed,
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
  const [localSearchTarget, setLocalSearchTarget] = useState("");
  const [localReconMode, setLocalReconMode] = useState<"passive" | "standard" | "aggressive">("standard");
  const [localTerminalOpen, setLocalTerminalOpen] = useState(true);
  const [localDataPanelOpen, setLocalDataPanelOpen] = useState(true);
  const [timelineMode, setTimelineMode] = useState(false);
  const [highlightType, setHighlightType] = useState("all");
  const [highlightMinConfidence, setHighlightMinConfidence] = useState(0);
  const [timeCursor, setTimeCursor] = useState(100);
  const [contextMenu, setContextMenu] = useState<ContextMenu | null>(null);
  const [contextTab, setContextTab] = useState<ContextTab>("transforms");
  const [runningTask, setRunningTask] = useState<string | null>(null);
  const [runningNodeId, setRunningNodeId] = useState<string | null>(null);
  const [dropHint, setDropHint] = useState(false);

  const effectiveSearchTarget = searchTarget ?? localSearchTarget;
  const effectiveSetSearchTarget = setSearchTarget ?? setLocalSearchTarget;
  const effectiveReconMode = reconMode ?? localReconMode;
  const effectiveSetReconMode = setReconMode ?? setLocalReconMode;
  const effectiveTerminalOpen = terminalOpen ?? localTerminalOpen;
  const effectiveSetTerminalOpen = setTerminalOpen ?? setLocalTerminalOpen;
  const effectiveDataPanelOpen = dataPanelOpen ?? localDataPanelOpen;
  const effectiveSetDataPanelOpen = setDataPanelOpen ?? setLocalDataPanelOpen;
  const selectedStrictNode = useMemo(() => graphNodes.find((node) => node.id === selectedNode?.id) || null, [graphNodes, selectedNode?.id]);
  const degreeById = useMemo(() => {
    const degree = new Map<string, number>();
    graphEdges.forEach((edge) => {
      degree.set(edge.source, (degree.get(edge.source) || 0) + 1);
      degree.set(edge.target, (degree.get(edge.target) || 0) + 1);
    });
    return degree;
  }, [graphEdges]);
  const timeBounds = useMemo(() => {
    const stamps = graphNodes.map(timestampForNode).filter((stamp) => stamp > 0).sort((a, b) => a - b);
    return { min: stamps[0] || 0, max: stamps[stamps.length - 1] || 0 };
  }, [graphNodes]);
  const temporalCutoff = useMemo(() => {
    if (!timeBounds.min || !timeBounds.max || timeBounds.min === timeBounds.max) return Number.POSITIVE_INFINITY;
    return timeBounds.min + ((timeBounds.max - timeBounds.min) * timeCursor) / 100;
  }, [timeBounds.max, timeBounds.min, timeCursor]);
  const temporalActive = Number.isFinite(temporalCutoff) && timeCursor < 100;
  const visibleNodeIds = useMemo(() => new Set(graphNodes.filter((node) => !temporalActive || timestampForNode(node) <= temporalCutoff).map((node) => node.id)), [graphNodes, temporalActive, temporalCutoff]);
  const timeMachineLabel = timeCursor >= 100 || !Number.isFinite(temporalCutoff) ? "live" : new Date(temporalCutoff).toLocaleString();

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
      effectiveSetDataPanelOpen(true);
    },
    [effectiveSetDataPanelOpen, onSelectNode],
  );

  const runLayout = useCallback((mode: LayoutMode = layoutMode, fit = true) => {
    const cy = cyRef.current;
    if (!cy || !cy.nodes().length) return;
    const common = { animate: true, animationDuration: 520, animationEasing: "ease-out", fit, padding: 110 };
    if (mode === "tree") {
      cy.layout({ name: "breadthfirst", directed: true, circle: false, spacingFactor: 2.0, avoidOverlap: true, ...common }).run();
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
          body: JSON.stringify({ investigation_id: investigationId, node_id: node.id, transform, mode: effectiveReconMode }),
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
    [effectiveReconMode, investigationId, onError, onTaskStart, pollGraphUntilComplete],
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
      style: ([
        {
          selector: "node",
          style: {
            width: 54,
            height: 54,
            shape: "data(nodeShape)",
            "background-color": "#111111",
            "background-opacity": 1,
            "background-image": "data(icon)",
            "background-fit": "contain",
            "background-width": "48px",
            "background-height": "48px",
            "background-position-x": "50%",
            "background-position-y": "50%",
            "border-width": 2,
            "border-color": "#555555",
            color: "#ffffff",
            label: "data(label)",
            "font-family": "JetBrains Mono, SFMono-Regular, Consolas, monospace",
            "font-size": 11,
            "font-weight": 600,
            "text-wrap": "wrap",
            "text-max-width": 156,
            "text-valign": "bottom",
            "text-halign": "center",
            "text-margin-y": 8,
            "text-background-color": "#000000",
            "text-background-opacity": 1,
            "text-background-padding": 3,
            "overlay-opacity": 0,
            opacity: 1,
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
          selector: "node.low-confidence",
          style: { "border-style": "dashed", "border-color": "#888888", color: "#888888" },
        },
        {
          selector: "node.censored-entity",
          style: { "border-style": "dashed", "border-color": "#888888", "background-color": "#111111" },
        },
        {
          selector: "node.location-entity",
          style: { "background-color": "#151515", "border-color": "#ffffff" },
        },
        {
          selector: "node.processing",
          style: { "border-width": 4, "border-color": "#ffffff" },
        },
        {
          selector: "node.hub-amber",
          style: { "border-width": 4, "border-color": "#f59e0b" },
        },
        {
          selector: "node.hub-red",
          style: { "border-width": 5, "border-color": "#ef4444" },
        },
        {
          selector: "node.tag-internal",
          style: { "border-color": "#facc15", color: "#facc15" },
        },
        {
          selector: "node.tag-suspicious",
          style: { "border-color": "#ef4444", "background-color": "#171111" },
        },
        {
          selector: "edge",
          style: {
            width: 1,
            "line-color": "#333333",
            "target-arrow-shape": "triangle",
            "target-arrow-color": "#555555",
            "target-arrow-width": 6,
            "arrow-scale": 0.72,
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
          selector: ".time-hidden",
          style: { display: "none", opacity: 0 },
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
      ] as unknown as cytoscape.StylesheetCSS[]),
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

      const original = event.originalEvent as MouseEvent | undefined;
      original?.preventDefault?.();
      original?.stopPropagation?.();

      const rect = containerRef.current.getBoundingClientRect();
      const renderedPosition = event.renderedPosition;
      const nodeRenderedPosition = event.target.renderedPosition();
      const hasRenderedPosition =
        renderedPosition &&
        Number.isFinite(renderedPosition.x) &&
        Number.isFinite(renderedPosition.y);
      const hasNodeRenderedPosition =
        nodeRenderedPosition &&
        Number.isFinite(nodeRenderedPosition.x) &&
        Number.isFinite(nodeRenderedPosition.y);

      const anchor = hasNodeRenderedPosition ? nodeRenderedPosition : hasRenderedPosition ? renderedPosition : null;
      const viewportX = anchor ? rect.left + anchor.x + 12 : original?.clientX ?? rect.left + rect.width / 2;
      const viewportY = anchor ? rect.top + anchor.y - 18 : original?.clientY ?? rect.top + rect.height / 2;

      selectStrictNode(strict);
      setContextTab("transforms");
      setContextMenu({ x: viewportX, y: viewportY, node: strict });
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
  }, [effectiveDataPanelOpen, effectiveTerminalOpen, resizeGraph, timelineMode]);

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
        const faded = highlightType !== "all" && (node.nodeType !== highlightType || confidenceLevelForNode(node) < highlightMinConfidence);
        const degree = degreeById.get(node.id) || 0;
        const hubClass = degree > 10 ? "hub-red" : degree > 5 ? "hub-amber" : "";
        const timeHidden = temporalActive && !visibleNodeIds.has(node.id);
        const classes = `${element.classes || ""} ${node.id === runningNodeId ? "processing" : ""} ${hubClass} ${faded ? "faded" : ""} ${timeHidden ? "time-hidden" : ""}`.trim();
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
        const edgeConfidence = edge.confidence_level || 60;
        const edgeTimestamp = timestampForEdge(edge);
        const timeHidden = temporalActive && (!visibleNodeIds.has(edge.source) || !visibleNodeIds.has(edge.target) || (edgeTimestamp > 0 && edgeTimestamp > temporalCutoff));
        const faded = highlightType !== "all" && ((typeById.get(edge.source) !== highlightType && typeById.get(edge.target) !== highlightType) || edgeConfidence < highlightMinConfidence);
        const element = edgeElement(edge, runningNodeId, faded);
        const classes = `${element.classes || ""} ${timeHidden ? "time-hidden" : ""}`.trim();
        if (existing.length) {
          existing.data(element.data || {});
          existing.classes(classes);
        } else {
          const added = cy.add({ ...element, classes });
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
  }, [degreeById, graphEdges, graphNodes, highlightMinConfidence, highlightType, layoutMode, resizeGraph, runLayout, runningNodeId, temporalActive, temporalCutoff, visibleNodeIds]);

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
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setContextMenu(null);
    };
    window.addEventListener("click", close);
    window.addEventListener("resize", close);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("click", close);
      window.removeEventListener("resize", close);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, []);


  useEffect(() => {
    const handleOracleCommand = (event: Event) => {
      const detail = (event as CustomEvent).detail || {};
      if (detail.type === "highlight_type" && detail.nodeType) {
        setHighlightType(String(detail.nodeType));
        setHighlightMinConfidence(Number(detail.minConfidence || 0));
        onSystemLog?.(`[ORACLE] Highlighting ${detail.nodeType}${detail.minConfidence ? ` above ${detail.minConfidence}% confidence` : ""}.`);
      }
      if (detail.type === "clear_highlight") {
        setHighlightType("all");
        setHighlightMinConfidence(0);
        onSystemLog?.("[ORACLE] Graph highlight cleared.");
      }
      if (detail.type === "suggest_transform" && detail.transform) {
        onSystemLog?.(`[ORACLE] Suggested transform ${detail.transform}${detail.reason ? `: ${detail.reason}` : ""}`);
      }
    };
    window.addEventListener("nexus:oracle-command", handleOracleCommand);
    return () => window.removeEventListener("nexus:oracle-command", handleOracleCommand);
  }, [onSystemLog]);

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
    if (!contextMenu) return { left: 0, top: 0 };
    const menuWidth = 342;
    const menuHeight = 430;
    const viewportMargin = 10;
    const nodeGap = 50;
    const toolbarSafeTop = 76;
    const viewportWidth = typeof window === "undefined" ? 1440 : window.innerWidth;
    const viewportHeight = typeof window === "undefined" ? 900 : window.innerHeight;

    const rightSideLeft = contextMenu.x + nodeGap;
    const leftSideLeft = contextMenu.x - menuWidth - nodeGap;
    const preferredLeft = rightSideLeft + menuWidth + viewportMargin > viewportWidth ? leftSideLeft : rightSideLeft;
    const preferredTop = contextMenu.y - 72;

    return {
      left: Math.max(viewportMargin, Math.min(preferredLeft, viewportWidth - menuWidth - viewportMargin)),
      top: Math.max(toolbarSafeTop, Math.min(preferredTop, viewportHeight - viewportMargin - Math.min(menuHeight, viewportHeight - viewportMargin * 2))),
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

        <form className="graph-launcher" onSubmit={onLaunch || ((event) => { event.preventDefault(); onError("Use the Command Center graph route to launch investigations."); })}>
          <Search size={15} />
          <input value={effectiveSearchTarget} onChange={(event) => effectiveSetSearchTarget(event.target.value)} placeholder="username, email, domain, IP, phone" />
          <select value={effectiveReconMode} onChange={(event) => effectiveSetReconMode(event.target.value as "passive" | "standard" | "aggressive")}>
            <option value="passive">Passive</option>
            <option value="standard">Standard</option>
            <option value="aggressive">Aggressive</option>
          </select>
          <button
            className="graph-add-button"
            type="button"
            disabled={Boolean(isLaunching) || !effectiveSearchTarget.trim()}
            onClick={() => {
              if (!onAddSeed) {
                onError("Add Entity is only available inside the Command Center graph route.");
                return;
              }
              void onAddSeed(effectiveSearchTarget.trim(), effectiveReconMode);
            }}
          >
            <Plus size={14} />
            <span>Add Entity</span>
          </button>
          <button className="graph-launch-button" type="submit" disabled={Boolean(isLaunching)}>
            <Radio size={14} />
            <span>{isLaunching ? "Running" : "Lookup"}</span>
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
            <select value={highlightType} onChange={(event) => { setHighlightType(event.target.value); setHighlightMinConfidence(0); }}>
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
            <button className={effectiveDataPanelOpen ? "icon-button active" : "icon-button"} type="button" onClick={() => effectiveSetDataPanelOpen((open) => !open)} title="Toggle entity data panel">
              <PanelRight size={16} />
            </button>
            <button className={effectiveTerminalOpen ? "icon-button active" : "icon-button"} type="button" onClick={() => effectiveSetTerminalOpen((open) => !open)} title="Toggle terminal HUD">
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

      {!timelineMode && graphNodes.length > 1 && (
        <div className="time-machine-slider" aria-label="Temporal playback slider">
          <div>
            <Clock3 size={13} />
            <span>Time Machine</span>
            <code>{timeMachineLabel}</code>
          </div>
          <input type="range" min="0" max="100" value={timeCursor} onChange={(event) => setTimeCursor(Number(event.target.value))} />
        </div>
      )}

      {contextMenu && typeof document !== "undefined" && createPortal(
        <div
          className="graph-context-menu"
          style={{ "--context-x": `${contextPosition.left}px`, "--context-y": `${contextPosition.top}px` } as CSSProperties}
          onClick={(event) => event.stopPropagation()}
          onContextMenu={(event) => event.preventDefault()}
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
        </div>,
        document.body,
      )}
    </section>
  );
}
