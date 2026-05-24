export type ToastMessage = { id: string; tone?: "info" | "success" | "warning" | "danger"; message: string };

export default function ToastHost({ toasts }: { toasts: ToastMessage[] }) {
  return <div className="toast-host" aria-live="polite">{toasts.map((toast) => <div className={`toast ${toast.tone || "info"}`} key={toast.id}>{toast.message}</div>)}</div>;
}

