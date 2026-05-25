import type { ReactNode } from "react";

export default function GraphWorkspaceLayout({ children }: { children: ReactNode }) {
  return <section className="nexus-graph-workspace graph-workspace-layout">{children}</section>;
}
