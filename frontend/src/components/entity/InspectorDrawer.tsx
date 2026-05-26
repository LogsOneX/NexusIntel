import type { ReactNode } from "react";

export default function InspectorDrawer({ open, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  return (
    <aside className={open ? "nexus-drawer-right inspector-drawer open" : "nexus-drawer-right inspector-drawer"} aria-label="Entity inspector drawer" aria-hidden={!open}>
      {children}
    </aside>
  );
}
