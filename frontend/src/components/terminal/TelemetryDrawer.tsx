import type { ReactNode } from "react";

export default function TelemetryDrawer({ open, children }: { open: boolean; children: ReactNode }) {
  return <section className={open ? "telemetry-drawer open" : "telemetry-drawer"} aria-label="Live telemetry" aria-hidden={!open}>{children}</section>;
}
