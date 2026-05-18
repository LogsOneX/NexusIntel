import { Terminal } from 'lucide-react';

export default function EventHud({ events }) {
  return (
    <section className="hud">
      <div className="panel-title">
        <Terminal size={16} />
        <span>Live Recon HUD</span>
      </div>
      <div className="hud-log">
        {events.slice(-120).map((event) => (
          <div className={`log-line ${event.level}`} key={event.id || `${event.created_at}-${event.message}`}>
            <span className="log-time">{formatTime(event.created_at)}</span>
            <span className="log-module">{event.module || 'system'}</span>
            <span className="log-message">{event.message}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function formatTime(value) {
  if (!value) return '--:--:--';
  const date = new Date(value);
  return date.toLocaleTimeString([], { hour12: false });
}
