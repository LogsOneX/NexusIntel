import type { ApiNode } from "./types";

export function confidenceScore(value?: string | number | null): number {
  if (typeof value === "number" && Number.isFinite(value)) return Math.max(0, Math.min(100, value));
  const raw = String(value || "").toLowerCase();
  if (["confirmed", "high", "success", "true", "verified"].includes(raw)) return 90;
  if (["medium", "observed", "probable"].includes(raw)) return 64;
  if (["low", "weak", "candidate", "false"].includes(raw)) return 34;
  return 45;
}

export function confidenceForNode(node?: ApiNode | null): number {
  if (!node) return 0;
  if (typeof node.confidence_level === "number") return confidenceScore(node.confidence_level);
  if (typeof node.data?.confidence_score === "number") return confidenceScore(node.data.confidence_score);
  if (typeof node.data?.confidence_level === "number") return confidenceScore(node.data.confidence_level);
  return confidenceScore(node.confidence);
}

export function confidenceLabel(score: number): string {
  if (score >= 95) return "confirmed";
  if (score >= 80) return "strong";
  if (score >= 60) return "probable";
  if (score >= 40) return "weak";
  return "noise risk";
}

export function confidenceTone(score: number): "critical" | "high" | "medium" | "low" | "muted" {
  if (score >= 80) return "high";
  if (score >= 60) return "medium";
  if (score >= 40) return "low";
  return "muted";
}

export function evidenceWarning(node?: ApiNode | null): string | null {
  if (!node) return null;
  const data = node.data || {};
  const artifact = (data.artifact || {}) as Record<string, unknown>;
  if (!data.source_url && !artifact.source_url && !data.raw_evidence_ref && !artifact.raw_evidence_ref) {
    return "No source URL or raw evidence reference is linked to this node yet.";
  }
  return null;
}

