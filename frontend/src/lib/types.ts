export type ApiNode = {
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

export type ApiEdge = {
  id: string;
  source: string;
  target: string;
  type: string;
  confidence?: string;
  confidence_level?: number;
  data?: Record<string, unknown>;
  created_at?: string;
};

export type GraphPayload = { nodes: ApiNode[]; edges: ApiEdge[]; leads?: ArtifactBinItem[]; noise?: ArtifactBinItem[]; compliance?: ArtifactBinItem[]; metadata?: GraphResponseMetadata };

export type ArtifactBinItem = {
  id?: string;
  classification?: string;
  artifact_class?: string;
  graph_visibility?: string;
  promotion_status?: string;
  type?: string;
  label?: string;
  value?: string;
  source?: string;
  source_url?: string | null;
  confidence?: string | number | null;
  confidence_score?: number | null;
  confidence_reason?: string | null;
  noise_reason?: string | null;
  relationship?: string | null;
  raw_evidence_ref?: string | null;
  legal_basis?: string | null;
  public_source_note?: string | null;
  parent_id?: string | null;
  created_at?: string | null;
  data?: Record<string, unknown>;
};

export type GraphResponseMetadata = {
  created_entity_ids?: string[];
  candidate_count?: number;
  noise_count?: number;
  compliance_count?: number;
};

export type TransformDefinition = {
  id: string;
  label: string;
  description: string;
  input_types: string[];
  output_types: string[];
  adapter_id?: string;
  source_category?: string;
  requires_api_key: boolean;
  required_keys?: string[];
  enabled: boolean;
  disabled_reason?: string | null;
  legal_note?: string;
  passive?: boolean;
  confidence_profile?: string;
  cost_profile?: string;
  runtime_profile?: string;
  estimated_runtime?: string;
  noise_risk?: string;
  evidence_behavior?: string;
  output_artifact_class?: string;
  recommended_next_transforms?: string[];
  playbook_id?: string | null;
};

export type EvidenceRecord = {
  id: string;
  investigation_id: string;
  entity_id?: string | null;
  source: string;
  uri: string;
  sha256: string;
  content_type: string;
  size_bytes: number;
  meta?: Record<string, unknown>;
  created_at: string;
  payload_preview?: string | null;
  payload_truncated?: boolean;
};

export type Investigation = {
  id: string;
  target: string;
  target_type: string;
  status: string;
  mode: string;
  created_at: string;
  updated_at: string;
  meta?: Record<string, unknown>;
};

export type GraphIntelligence = {
  posture: string;
  risk_score: number;
  source_reliability: number;
  lead_queue: Array<{ priority: string; node_id: string; label: string; action: string; reason: string }>;
  entity_risks: Array<Record<string, unknown>>;
  communities: Array<{ id: string; size: number; hub_id: string; hub_label: string; types: Record<string, number> }>;
  dossier: Record<string, unknown>;
};

export type CaseHealth = {
  score: number;
  status: string;
  node_count: number;
  edge_count: number;
  coverage: Record<string, number>;
  weak_nodes: Array<Record<string, unknown>>;
  isolated_nodes: Array<Record<string, unknown>>;
  recommendations: Array<{ priority: string; action: string; reason: string }>;
  intelligence?: GraphIntelligence;
};

export type CoverageMatrixData = {
  columns: string[];
  rows: string[];
  matrix: Record<string, Record<string, number>>;
};

export type AnalystPipeline = {
  generated_at: string;
  selected_entity: {
    entity_id?: string;
    entity_type: string;
    confidence_baseline: number;
    confidence_label?: string;
    source?: string;
    source_url?: string;
    timestamp?: string;
    raw_evidence_ref?: string;
    confidence_reason?: string;
    legal_note?: string;
    source_coverage_status: string[];
    available_transforms: TransformDefinition[];
    recommended_transforms: TransformDefinition[];
    disabled_transforms: TransformDefinition[];
    noise?: { is_noise: boolean; noise_score: number; reasons: string[] };
  };
  coverage_matrix: CoverageMatrixData;
  noise_killer: { filtered_count: number; items: Array<Record<string, unknown>> };
  correlations: Array<Record<string, unknown>>;
  lead_queue: {
    strongest_pivots: Array<Record<string, unknown>>;
    unverified_interesting_pivots: Array<Record<string, unknown>>;
    possible_same_actor_links: Array<Record<string, unknown>>;
    contradictions: Array<Record<string, unknown>>;
    high_value_next_actions: Array<Record<string, unknown>>;
  };
  evidence_summary: { count: number; sources: Record<string, number>; hashes: string[] };
};

export type TerminalLine = {
  task_id?: string;
  level: string;
  message: string;
  time?: string;
  payload?: Record<string, unknown>;
};

export type SessionState = { token: string | null; user: string | null };

export type PageProps = {
  token: string;
  user: string;
  navigate: (path: string) => void;
};

export type CommandItem = {
  id: string;
  label: string;
  description?: string;
  shortcut?: string;
  group?: string;
  disabled?: boolean;
  action: () => void;
};

export type ConnectorDefinition = {
  id: string;
  name: string;
  category: string;
  reliability?: string;
  source_reliability?: string;
  legal_note: string;
  requires_key?: boolean;
  requires_api_key?: boolean;
  configured?: boolean;
  enabled?: boolean;
  key_present?: boolean;
  testable?: boolean;
  implemented?: boolean;
  test_status?: string;
  last_tested?: string | null;
  last_error?: string | null;
  unlocked_transforms?: TransformDefinition[];
  quota?: string;
  quota_placeholder?: string;
  documentation_url?: string | null;
  disabled_reason?: string | null;
};


export type SourceCapability = {
  id: string;
  name: string;
  row: string;
  source_mode: "LOCAL_NATIVE" | "PUBLIC_PASSIVE" | "BROWSER_ASSISTED" | "IMPORTED_EVIDENCE" | "OPTIONAL_BYOK";
  cost_profile: string;
  requires_api_key: boolean;
  requires_browser: boolean;
  passive: boolean;
  input_types: string[];
  output_types: string[];
  evidence_behavior: string;
  noise_risk: string;
  legal_note: string;
  enabled: boolean;
  disabled_reason?: string | null;
};

export type SourceCapabilityMatrix = {
  rows: string[];
  columns: SourceCapability["source_mode"][];
  matrix: Record<string, Record<string, SourceCapability[]>>;
};
