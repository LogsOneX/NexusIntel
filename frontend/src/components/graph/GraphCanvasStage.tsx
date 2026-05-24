import type { ReactNode } from "react";

export default function GraphCanvasStage({ children }: { children: ReactNode }) {
  return <main className="graph-canvas-stage">{children}</main>;
}
