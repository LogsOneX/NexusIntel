import { AlertTriangle } from "lucide-react";

export default function ConfirmDialog({ open, title, message, confirmLabel = "Confirm", tone = "danger", onConfirm, onCancel }: { open: boolean; title: string; message: string; confirmLabel?: string; tone?: "danger" | "neutral"; onConfirm: () => void; onCancel: () => void }) {
  if (!open) return null;
  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onCancel}>
      <section className="confirm-dialog" role="dialog" aria-modal="true" aria-labelledby="confirm-title" onMouseDown={(event) => event.stopPropagation()}>
        <header><AlertTriangle size={18} /><strong id="confirm-title">{title}</strong></header>
        <p>{message}</p>
        <footer><button type="button" onClick={onCancel}>Cancel</button><button className={tone === "danger" ? "danger" : ""} type="button" onClick={onConfirm}>{confirmLabel}</button></footer>
      </section>
    </div>
  );
}

