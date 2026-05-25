import { X } from "lucide-react";
import type { ReactNode } from "react";

export default function InspectorDrawer({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  return (
    <aside className={open ? "nexus-drawer-right inspector-drawer open" : "nexus-drawer-right inspector-drawer"} aria-label="Entity inspector drawer" aria-hidden={!open}>
      <button className="drawer-close" type="button" onClick={onClose} aria-label="Close inspector"><X size={15} /></button>
      {children}
    </aside>
  );
}
