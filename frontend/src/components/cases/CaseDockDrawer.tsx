import type { ReactNode } from "react";

export default function CaseDockDrawer({ open, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  return (
    <aside className={open ? "nexus-drawer-left case-dock-drawer open" : "nexus-drawer-left case-dock-drawer"} aria-label="Case dock" aria-hidden={!open}>
      {children}
    </aside>
  );
}
