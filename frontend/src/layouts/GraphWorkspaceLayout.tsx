import type { ReactNode } from "react";

export default function GraphWorkspaceLayout({ children }: { children: ReactNode }) {
  return <section className="graph-workspace-layout">{children}</section>;
}
