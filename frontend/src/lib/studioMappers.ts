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
