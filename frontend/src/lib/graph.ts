import type { ApiNode, EvidenceRecord, GraphPayload, CoverageMatrixData, CaseHealth } from "./types";

export function flattenData(input: unknown, prefix = ""): Array<[string, string]> {
  if (input === null || input === undefined) return [];
  if (typeof input !== "object") return [[prefix || "value", String(input)]];
  if (Array.isArray(input)) return input.flatMap((item, index) => flattenData(item, `${prefix}[${index}]`));
  return Object.entries(input as Record<string, unknown>).flatMap(([key, value]) => {
    const nextKey = prefix ? `${prefix}.${key}` : key;
    if (value && typeof value === "object") return flattenData(value, nextKey);
    return [[nextKey, String(value ?? "")]];
  });
}

export function classifyEntityValue(value: string): string {
  const target = value.trim();
  if (/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(target)) return "email";
  if (/^\+[1-9]\d{7,14}$/.test(target.replace(/[\s-]/g, ""))) return "phone";
  if (/^(?:\d{1,3}\.){3}\d{1,3}$/.test(target) || target.includes(":")) return "ip";
  if (/^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$/i.test(target.replace(/^https?:\/\//, "").split("/")[0])) return "domain";
  return target.includes(" ") ? "name" : "username";
}

export const COVERAGE_COLUMNS = ["Email", "Username", "Phone", "Domain", "IP", "Image", "Maps", "Breach", "Web", "Infrastructure", "Social", "Code", "Crypto"];
export const COVERAGE_ROWS = ["attempted", "found", "verified", "noisy", "disabled", "requires API key"];

function familyForType(type: string): string {
  const normalized = type.toLowerCase();
  if (normalized.includes("email")) return "Email";
  if (["username", "profile", "profile_candidate", "name"].includes(normalized) || normalized.includes("social")) return "Username";
  if (normalized.includes("phone")) return "Phone";
  if (normalized.includes("domain") || normalized.includes("dns")) return "Domain";
  if (normalized === "ip" || normalized.includes("asn")) return "IP";
  if (normalized.includes("image") || normalized.includes("avatar") || normalized.includes("favicon")) return "Image";
  if (normalized.includes("maps") || normalized.includes("google_review") || normalized.includes("location")) return "Maps";
  if (normalized.includes("breach")) return "Breach";
  if (normalized.includes("url") || normalized.includes("web")) return "Web";
  if (normalized.includes("cert") || normalized.includes("rdap") || normalized.includes("tls")) return "Infrastructure";
  if (normalized.includes("code") || normalized.includes("github") || normalized.includes("gitlab")) return "Code";
  if (normalized.includes("crypto") || normalized.includes("wallet") || normalized.includes("transaction")) return "Crypto";
  return "Web";
}

export function inferCoverageMatrix(graph?: GraphPayload | null, health?: CaseHealth | null): CoverageMatrixData {
  const matrix: CoverageMatrixData = {
    columns: COVERAGE_COLUMNS,
    rows: COVERAGE_ROWS,
    matrix: Object.fromEntries(COVERAGE_ROWS.map((row) => [row, Object.fromEntries(COVERAGE_COLUMNS.map((column) => [column, 0]))])),
  };
  if (health?.coverage) {
    Object.entries(health.coverage).forEach(([key, value]) => {
      const column = COVERAGE_COLUMNS.find((item) => item.toLowerCase() === key.toLowerCase()) || familyForType(key);
      matrix.matrix.found[column] = Number(value || 0);
      if (Number(value || 0) > 0) matrix.matrix.attempted[column] = Math.max(1, matrix.matrix.attempted[column]);
    });
  }
  (graph?.nodes || []).forEach((node) => {
    const column = familyForType(node.type);
    matrix.matrix.found[column] += 1;
    matrix.matrix.attempted[column] = Math.max(matrix.matrix.attempted[column], 1);
    const confidence = String(node.confidence || node.data?.confidence || "").toLowerCase();
    if (["confirmed", "high", "verified"].includes(confidence)) matrix.matrix.verified[column] += 1;
    if (["noise", "low"].includes(confidence) || node.data?.noise === true) matrix.matrix.noisy[column] += 1;
  });
  return matrix;
}

export function evidenceRefsForNode(node: ApiNode | null | undefined): string[] {
  if (!node) return [];
  const data = node.data || {};
  const artifact = (data.artifact || {}) as Record<string, unknown>;
  return [data.raw_evidence_ref, artifact.raw_evidence_ref, data.evidence_id, artifact.evidence_id].filter(Boolean).map(String);
}

export function deriveEvidenceFromGraph(graph: GraphPayload, investigationId = "local"): EvidenceRecord[] {
  return graph.nodes.flatMap((node) => {
    const data = node.data || {};
    const artifact = (data.artifact || {}) as Record<string, unknown>;
    const sourceUrl = String(data.source_url || artifact.source_url || data.final_url || "");
    const hash = String(data.payload_sha256 || artifact.payload_sha256 || data.sha256 || "");
    if (!sourceUrl && !hash) return [];
    return [{
      id: String(data.raw_evidence_ref || artifact.raw_evidence_ref || `${node.id}:derived-evidence`),
      investigation_id: investigationId,
      entity_id: node.id,
      source: String(node.source || data.source || artifact.source || "graph-node"),
      uri: sourceUrl || "local graph metadata",
      sha256: hash || "hash pending",
      content_type: String(data.content_type || artifact.content_type || "metadata/json"),
      size_bytes: Number(data.size_bytes || artifact.size_bytes || 0),
      meta: { derived_from_node: node.id, legal_note: data.legal_basis || data.legal_note || artifact.legal_basis },
      created_at: String(data.fetched_at || node.created_at || new Date().toISOString()),
      payload_preview: null,
      payload_truncated: false,
    }];
  });
}

