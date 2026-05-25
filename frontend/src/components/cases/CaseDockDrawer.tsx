import { X } from "lucide-react";
import type { ReactNode } from "react";

export default function CaseDockDrawer({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  return (
    <aside className={open ? "nexus-drawer-left case-dock-drawer open" : "nexus-drawer-left case-dock-drawer"} aria-label="Case dock" aria-hidden={!open}>
      <button className="drawer-close" type="button" onClick={onClose} aria-label="Close case dock"><X size={15} /></button>
      {children}
    </aside>
  );
}
