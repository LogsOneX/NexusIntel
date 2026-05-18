import { Activity, Database, Play, Plus, Radar, Search } from 'lucide-react';

export default function Sidebar({
  target,
  mode,
  investigations,
  active,
  schema,
  manual,
  onTarget,
  onMode,
  onCreate,
  onSelectInvestigation,
  onManualChange,
  onAddManual
}) {
  return (
    <aside className="sidebar">
      <div className="brand">
        <div className="brand-mark">NX</div>
        <div>
          <strong>NexusIntel</strong>
          <span>Autonomous OSINT Graph</span>
        </div>
      </div>

      <section className="panel">
        <div className="panel-title">
          <Radar size={16} />
          <span>New Investigation</span>
        </div>
        <input value={target} onChange={(event) => onTarget(event.target.value)} placeholder="username, email, domain, URL, phone" />
        <div className="segmented">
          {['standard', 'active', 'aggressive'].map((item) => (
            <button key={item} className={mode === item ? 'selected' : ''} onClick={() => onMode(item)}>
              {item}
            </button>
          ))}
        </div>
        <button className="primary wide" onClick={onCreate}>
          <Play size={16} />
          Launch Hunt
        </button>
      </section>

      <section className="panel grow">
        <div className="panel-title">
          <Activity size={16} />
          <span>Cases</span>
        </div>
        <div className="case-list">
          {investigations.map((item) => (
            <button
              key={item.id}
              className={`case-item ${active?.id === item.id ? 'selected' : ''}`}
              onClick={() => onSelectInvestigation(item.id)}
            >
              <strong>{item.target}</strong>
              <span>{item.target_type} · {item.mode} · {item.status}</span>
            </button>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-title">
          <Plus size={16} />
          <span>Add Entity</span>
        </div>
        <select value={manual.type} onChange={(event) => onManualChange({ ...manual, type: event.target.value })}>
          {(schema.entity_types || []).map((type) => (
            <option key={type} value={type}>{type}</option>
          ))}
        </select>
        <input value={manual.value} onChange={(event) => onManualChange({ ...manual, value: event.target.value })} placeholder="entity value" />
        <button className="ghost wide" disabled={!active} onClick={onAddManual}>
          <Plus size={15} />
          Add To Graph
        </button>
      </section>

      <section className="panel stats">
        <div className="panel-title">
          <Database size={16} />
          <span>Schema</span>
        </div>
        <div className="schema-tags">
          {(schema.modules || []).map((module) => <span key={module}>{module}</span>)}
        </div>
      </section>
    </aside>
  );
}
