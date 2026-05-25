import type { ApiEdge, ApiNode, ArtifactBinItem, TransformDefinition } from "./types";
import { entityLabelFor } from "./entityTypes";

export type UiNode = {
  id: string;
  type: string;
  label: string;
  value: string;
  confidence: number;
  source: string;
  sourceUrl?: string | null;
  evidenceRef?: string | null;
  raw: ApiNode;
};

export type UiEdge = {
  id: string;
  source: string;
  target: string;
  label: string;
  confidence: number;
  raw: ApiEdge;
};

export type UiBinItem = {
  id: string;
  type: string;
  label: string;
  value: string;
  reason: string;
  confidence: number;
  source?: string | null;
  sourceUrl?: string | null;
  raw: ArtifactBinItem;
};

export type UiTransform = {
  id: string;
  label: string;
  description: string;
  inputTypes: string[];
  outputTypes: string[];
  enabled: boolean;
  requiresApiKey: boolean;
  disabledReason?: string | null;
  raw: TransformDefinition;
};

function confidenceFrom(value: unknown): number {
  if (typeof value === "number" && Number.isFinite(value)) return Math.max(0, Math.min(100, value));
  const clean = String(value || "").toLowerCase();
  if (["confirmed", "verified", "high", "strong", "success"].includes(clean)) return 90;
  if (["medium", "probable", "observed"].includes(clean)) return 60;
  if (["low", "weak", "candidate"].includes(clean)) return 35;
  return 0;
}

export function mapApiNodeToUiNode(node: ApiNode): UiNode {
  const data = node.data || {};
  return {
    id: node.id,
    type: node.type,
    label: node.label || node.value || entityLabelFor(node.type),
    value: node.value || node.label || "",
    confidence: confidenceFrom(node.confidence_level ?? data.confidence_score ?? node.confidence),
    source: node.source || String(data.source || "graph"),
    sourceUrl: String(data.source_url || data.final_url || "") || null,
    evidenceRef: String(data.raw_evidence_ref || data.evidence_id || data.payload_sha256 || "") || null,
    raw: node,
  };
}

export function mapApiEdgeToUiEdge(edge: ApiEdge): UiEdge {
  return {
    id: edge.id,
    source: edge.source,
    target: edge.target,
    label: edge.type,
    confidence: confidenceFrom(edge.confidence_level ?? edge.data?.confidence_score ?? edge.confidence),
    raw: edge,
  };
}

function mapBinItem(item: ArtifactBinItem, fallbackReason: string): UiBinItem {
  return {
    id: item.id || item.raw_evidence_ref || `${item.type || item.artifact_class || "item"}:${item.value || item.label || "unkeyed"}`,
    type: item.type || item.artifact_class || item.classification || "artifact",
    label: item.label || item.value || item.type || "Artifact",
    value: item.value || item.label || "",
    reason: item.confidence_reason || item.noise_reason || fallbackReason,
    confidence: confidenceFrom(item.confidence_score ?? item.confidence),
    source: item.source,
    sourceUrl: item.source_url || null,
    raw: item,
  };
}

export function mapApiLeadToUiLead(item: ArtifactBinItem): UiBinItem {
  return mapBinItem(item, "Candidate lead requires analyst review before graph promotion.");
}

export function mapApiNoiseToUiNoise(item: ArtifactBinItem): UiBinItem {
  return mapBinItem(item, "Suppressed by noise filtering.");
}

export function mapApiComplianceToUiCompliance(item: ArtifactBinItem): UiBinItem {
  return mapBinItem(item, "Compliance or legal guardrail event.");
}

export function mapTransformRegistryToUiTransforms(transform: TransformDefinition): UiTransform {
  return {
    id: transform.id,
    label: transform.label,
    description: transform.description,
    inputTypes: transform.input_types || [],
    outputTypes: transform.output_types || [],
    enabled: transform.enabled,
    requiresApiKey: Boolean(transform.requires_api_key),
    disabledReason: transform.disabled_reason,
    raw: transform,
  };
}
