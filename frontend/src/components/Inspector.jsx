import { Crosshair, Network, ShieldAlert, Trash2, Zap } from 'lucide-react';

export default function Inspector({ selected, active, onExpand, onRemove }) {
  return (
    <section className="inspector">
      <div className="panel-title">
        <Crosshair size={16} />
        <span>Entity Inspector</span>
      </div>
      {!selected ? (
        <div className="empty-state">Select a graph node to inspect, expand, or remove it.</div>
      ) : (
        <>
          <div className="entity-heading">
            <div className="entity-type">{selected.type}</div>
            <h2>{selected.label}</h2>
            <p>{selected.value}</p>
          </div>
          <div className="metric-grid compact">
            <div>
              <span>Confidence</span>
              <strong>{selected.confidence}%</strong>
            </div>
            <div>
              <span>Source</span>
              <strong>{selected.source}</strong>
            </div>
          </div>
          <div className="action-row">
            <button className="primary" disabled={!active} onClick={onExpand}>
              <Zap size={15} />
              Expand
            </button>
            <button className="ghost danger" disabled={!active} onClick={onRemove}>
              <Trash2 size={15} />
              Remove
            </button>
          </div>
          <div className="json-box">
            <pre>{JSON.stringify(selected.properties || {}, null, 2)}</pre>
          </div>
        </>
      )}
      <div className="guardrail">
        <ShieldAlert size={15} />
        Public-source only. Active mode is read-only and intended for owned or authorized targets.
      </div>
      <div className="guardrail">
        <Network size={15} />
        Drag nodes directly on the canvas; expansions create new graph evidence.
      </div>
    </section>
  );
}
