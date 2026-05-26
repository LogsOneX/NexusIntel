import type { ViewportPoint } from "./viewportMath";

export function graphPositionStorageKey(investigationId: string | null | undefined): string {
  return `nexus.graph.positions.${investigationId || "detached"}`;
}

export function readGraphPositions(key: string): Record<string, ViewportPoint> {
  if (typeof window === "undefined") return {};
  try {
    const raw = window.localStorage.getItem(key);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as Record<string, ViewportPoint>;
    return Object.fromEntries(Object.entries(parsed || {}).filter(([, value]) => Number.isFinite(value?.x) && Number.isFinite(value?.y)));
  } catch {
    return {};
  }
}

export function writeGraphPositions(key: string, positions: Record<string, ViewportPoint>): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, JSON.stringify(positions));
  } catch {
    // Position persistence is a convenience layer; ignore quota/private-mode failures.
  }
}
