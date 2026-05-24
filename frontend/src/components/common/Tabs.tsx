export type TabItem = { id: string; label: string; count?: number };

export default function Tabs({ items, active, onChange, ariaLabel = "Tabs" }: { items: TabItem[]; active: string; onChange: (id: string) => void; ariaLabel?: string }) {
  return (
    <div className="premium-tabs" role="tablist" aria-label={ariaLabel}>
      {items.map((item) => (
        <button key={item.id} role="tab" aria-selected={active === item.id} className={active === item.id ? "active" : ""} type="button" onClick={() => onChange(item.id)}>
          {item.label}{typeof item.count === "number" && <span>{item.count}</span>}
        </button>
      ))}
    </div>
  );
}

