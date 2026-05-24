export type EntityShape = "circle" | "square" | "hexagon" | "triangle";

export type GraphNode = {
  id: string;
  nodeType: string;
  nodeLabel: string;
  nodeProperties: Record<string, unknown>;
  nodeShape: EntityShape;
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

export type LayoutMode = "tree" | "circular" | "force";
export type ContextTab = "transforms" | "playbooks";
