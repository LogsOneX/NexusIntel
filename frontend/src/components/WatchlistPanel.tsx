import { Radar } from "lucide-react";

type WatchlistItem = { id: string; target: string; target_type: string; enabled: boolean; interval_hours: number; last_delta?: Record<string, unknown> };

export default function WatchlistPanel({ items = [] }: { items?: WatchlistItem[] }) {
  return (
    <section className="flat-intel-panel">
      <header><Radar size={14} /><strong>Watchlist</strong></header>
      <div className="watchlist-rows">
        {items.map((item) => (
          <div className="watchlist-row" key={item.id}>
            <strong>{item.target}</strong>
            <span>{item.target_type} / {item.enabled ? "ON" : "OFF"} / {item.interval_hours}h</span>
          </div>
        ))}
        {!items.length && <p>No persistent surveillance targets configured.</p>}
      </div>
    </section>
  );
}
