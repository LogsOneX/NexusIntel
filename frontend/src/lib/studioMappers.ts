import type { ArtifactBinItem, Investigation, TransformDefinition } from "./types";
import {
  mapApiComplianceToUiCompliance,
  mapApiEdgeToUiEdge,
  mapApiLeadToUiLead,
  mapApiNodeToUiNode,
  mapApiNoiseToUiNoise,
  mapTransformRegistryToUiTransforms,
} from "./viewMappers";

export function mapApiNodeToStudioNode(node: unknown, _index = 0) {
  return mapApiNodeToUiNode(node as any);
}

export function mapApiEdgeToStudioEdge(edge: unknown, _index = 0) {
  return mapApiEdgeToUiEdge(edge as any);
}

export function mapApiCaseToStudioCase(item: Investigation | Record<string, unknown> | null | undefined) {
  const record = (item || {}) as Partial<Investigation> & Record<string, unknown>;
  const meta = (record.meta || {}) as Record<string, unknown>;
  return {
    id: String(record.id || ""),
    title: String(meta.case_name || record.target || "Detached workspace"),
    target: String(record.target || ""),
    targetType: String(record.target_type || "entity"),
    status: String(record.status || "unknown"),
    updatedAt: String(record.updated_at || ""),
    operator: String(meta.assigned_operator || "Operator"),
    raw: record,
  };
}

export function mapApiLeadToStudioLead(item: ArtifactBinItem | unknown, _index = 0) {
  return mapApiLeadToUiLead(item as ArtifactBinItem);
}

export function mapApiNoiseToStudioNoise(item: ArtifactBinItem | unknown, _index = 0) {
  return mapApiNoiseToUiNoise(item as ArtifactBinItem);
}

export function mapApiComplianceToStudioCompliance(item: ArtifactBinItem | unknown, _index = 0) {
  return mapApiComplianceToUiCompliance(item as ArtifactBinItem);
}

export function mapTransformRegistryToStudioTransforms(items: TransformDefinition[] | unknown[] | null | undefined) {
  return (Array.isArray(items) ? items : []).map((item) => mapTransformRegistryToUiTransforms(item as TransformDefinition));
}


export type StudioNodeVisual = { accent: string; code: string; icon: string; family: string };

const STUDIO_VISUALS: Record<string, StudioNodeVisual> = {
  username: { accent: "#3B82F6", code: "USER", icon: "fingerprint", family: "identity" },
  person_alias: { accent: "#3B82F6", code: "ALIAS", icon: "identity", family: "identity" },
  profile: { accent: "#3B82F6", code: "PROF", icon: "fingerprint", family: "identity" },
  email: { accent: "#10B981", code: "EMAIL", icon: "mail", family: "contact" },
  phone: { accent: "#10B981", code: "PHONE", icon: "phone", family: "contact" },
  domain: { accent: "#A855F7", code: "DNS", icon: "globe", family: "infra" },
  url: { accent: "#A855F7", code: "URL", icon: "link", family: "infra" },
  ip: { accent: "#A855F7", code: "IP", icon: "server", family: "infra" },
  google_maps_profile: { accent: "#F59E0B", code: "MAPS", icon: "pin", family: "geo" },
  location: { accent: "#F59E0B", code: "LOC", icon: "pin", family: "geo" },
  image_asset: { accent: "#F59E0B", code: "IMG", icon: "image", family: "asset" },
  crypto_wallet: { accent: "#10B981", code: "WALLET", icon: "wallet", family: "crypto" },
  indicator: { accent: "#EF4444", code: "IOC", icon: "alert", family: "threat" },
  evidence: { accent: "#8B8B91", code: "EV", icon: "file", family: "asset" },
};

export function getNodeConfidence(apiNode: any): number {
  const data = apiNode?.data || {};
  const numeric = Number(apiNode?.confidence_level ?? data.confidence_score ?? data.confidence_level);
  if (Number.isFinite(numeric)) return Math.max(0, Math.min(100, numeric));
  const clean = String(apiNode?.confidence || "").toLowerCase();
  if (["confirmed", "verified", "high", "strong", "success"].includes(clean)) return 90;
  if (["medium", "observed", "probable"].includes(clean)) return 60;
  if (["low", "weak", "candidate"].includes(clean)) return 30;
  return 50;
}

export function getNodeVisual(type: string): StudioNodeVisual {
  const clean = String(type || "").toLowerCase();
  if (clean.includes("risk") || clean.includes("suspicious")) return { accent: "#EF4444", code: "RISK", icon: "alert", family: "threat" };
  if (clean.includes("candidate") || clean.includes("possible")) return { accent: "#F59E0B", code: "LEAD", icon: "target", family: "candidate" };
  return STUDIO_VISUALS[clean] || { accent: "#3B82F6", code: "ENTITY", icon: "target", family: "identity" };
}

export function getNodeGlyph(type: string): string {
  return getNodeVisual(type).icon;
}

export function getNodeRisk(apiNode: any): "INTERNAL" | "SUSPICIOUS" | null {
  const value = String(apiNode?.value || apiNode?.label || "").toLowerCase();
  if (apiNode?.type === "ip" && (/^(10|127|0)\./.test(value) || /^192\.168\./.test(value) || /^172\.(1[6-9]|2\d|3[01])\./.test(value))) return "INTERNAL";
  if (apiNode?.type === "domain" && ["login-", "secure-", "verify-", "account-", "wallet-", "signin-", "-login", "-verify"].some((term) => value.includes(term))) return "SUSPICIOUS";
  return null;
}

export function mapStudioNodeToApiNode(studioNode: any) {
  return studioNode?.raw || studioNode?.api || studioNode;
}

export const getStudioNodeConfidence = getNodeConfidence;
export const getStudioNodeVisual = getNodeVisual;
export const getStudioNodeIcon = getNodeGlyph;
export const getStudioNodeRisk = getNodeRisk;
