import type { ReactNode } from "react";

export default function GraphCanvasStage({ children }: { children: ReactNode }) {
  return <main className="nexus-graph-stage osint-grid graph-canvas-stage">{children}</main>;
}
