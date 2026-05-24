import { X } from "lucide-react";

export default function Drawer({ open, title, children, onClose }: { open: boolean; title: string; children: React.ReactNode; onClose: () => void }) {
  return (
    <aside className={open ? "drawer-panel open" : "drawer-panel"} aria-hidden={!open}>
      <header><strong>{title}</strong><button type="button" onClick={onClose} aria-label="Close drawer"><X size={15} /></button></header>
      <div>{children}</div>
    </aside>
  );
}

