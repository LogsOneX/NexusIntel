import { Maximize2, RefreshCw, Search, Shield, Workflow } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import GraphCanvas from './components/GraphCanvas.jsx';
import EventHud from './components/EventHud.jsx';
import Inspector from './components/Inspector.jsx';
import Sidebar from './components/Sidebar.jsx';
import {
  addEntity,
  createInvestigation,
  expandEntity,
  getGraph,
  getInvestigation,
  getSchema,
  listInvestigations,
  removeEntity
} from './lib/api.js';

export default function App() {
  const [target, setTarget] = useState('');
  const [mode, setMode] = useState('standard');
  const [schema, setSchema] = useState({ entity_types: [], modules: [] });
  const [investigations, setInvestigations] = useState([]);
  const [active, setActive] = useState(null);
  const [graph, setGraph] = useState({ nodes: [], edges: [], summary: { nodes: 0, edges: 0, types: {} } });
  const [events, setEvents] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [filter, setFilter] = useState('');
  const [search, setSearch] = useState('');
  const [manual, setManual] = useState({ type: 'signal', value: '' });
  const [error, setError] = useState('');

  const selected = useMemo(() => graph.nodes.find((node) => node.id === selectedId), [graph.nodes, selectedId]);

  const refreshInvestigations = useCallback(async () => {
    const rows = await listInvestigations();
    setInvestigations(rows);
    return rows;
  }, []);

  const loadGraph = useCallback(async (id) => {
    if (!id) return;
    const payload = await getGraph(id);
    setGraph(payload);
  }, []);

  const selectInvestigation = useCallback(async (id) => {
    const item = await getInvestigation(id);
    setActive(item);
    setMode(item.mode);
    setSelectedId(null);
    await loadGraph(id);
  }, [loadGraph]);

  useEffect(() => {
    getSchema().then(setSchema).catch((err) => setError(err.message));
    refreshInvestigations()
      .then((rows) => {
        if (rows[0]) return selectInvestigation(rows[0].id);
        return null;
      })
      .catch((err) => setError(err.message));
  }, [refreshInvestigations, selectInvestigation]);

  useEffect(() => {
    if (!active?.id) return undefined;
    setEvents([]);
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const socket = new WebSocket(`${protocol}://${window.location.host}/api/investigations/${active.id}/ws`);
    socket.onmessage = (event) => {
      const parsed = JSON.parse(event.data);
      if (parsed.level === 'heartbeat') return;
      setEvents((items) => [...items.slice(-180), parsed]);
      loadGraph(active.id).catch(() => {});
      refreshInvestigations().catch(() => {});
    };
    socket.onerror = () => socket.close();
    const interval = setInterval(() => {
      loadGraph(active.id).catch(() => {});
      refreshInvestigations().catch(() => {});
    }, 5000);
    return () => {
      clearInterval(interval);
      socket.close();
    };
  }, [active?.id, loadGraph, refreshInvestigations]);

  async function launch() {
    if (!target.trim()) return;
    try {
      setError('');
      const item = await createInvestigation(target.trim(), mode);
      await refreshInvestigations();
      await selectInvestigation(item.id);
      setTarget('');
    } catch (err) {
      setError(err.message);
    }
  }

  async function expandSelected() {
    if (!active?.id || !selectedId) return;
    try {
      await expandEntity(active.id, selectedId, mode);
    } catch (err) {
      setError(err.message);
    }
  }

  async function addManualEntity() {
    if (!active?.id || !manual.value.trim()) return;
    try {
      await addEntity(active.id, {
        ...manual,
        value: manual.value.trim(),
        source_entity_id: selectedId,
        relationship_type: 'manual_link'
      });
      setManual({ ...manual, value: '' });
      await loadGraph(active.id);
    } catch (err) {
      setError(err.message);
    }
  }

  async function removeSelected() {
    if (!active?.id || !selectedId) return;
    try {
      await removeEntity(active.id, selectedId);
      setSelectedId(null);
      await loadGraph(active.id);
    } catch (err) {
      setError(err.message);
    }
  }

  const typeOptions = Object.entries(graph.summary?.types || {}).sort((a, b) => b[1] - a[1]);

  return (
    <div className="app-shell">
      <Sidebar
        target={target}
        mode={mode}
        investigations={investigations}
        active={active}
        schema={schema}
        manual={manual}
        onTarget={setTarget}
        onMode={setMode}
        onCreate={launch}
        onSelectInvestigation={selectInvestigation}
        onManualChange={setManual}
        onAddManual={addManualEntity}
      />

      <main className="workspace">
        <header className="topbar">
          <div>
            <div className="eyebrow">
              <Shield size={15} />
              public-source autonomous link analysis
            </div>
            <h1>{active ? active.target : 'No active investigation'}</h1>
          </div>
          <div className="metric-grid">
            <div><span>Nodes</span><strong>{graph.summary?.nodes || 0}</strong></div>
            <div><span>Edges</span><strong>{graph.summary?.edges || 0}</strong></div>
            <div><span>Status</span><strong>{active?.status || 'idle'}</strong></div>
            <div><span>Mode</span><strong>{active?.mode || mode}</strong></div>
          </div>
        </header>

        {error && <div className="error-banner">{error}</div>}

        <section className="graph-panel">
          <div className="graph-toolbar">
            <div className="panel-title">
              <Workflow size={16} />
              <span>Visual Link Analysis</span>
            </div>
            <div className="toolbar-controls">
              <label className="searchbox">
                <Search size={15} />
                <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search graph" />
              </label>
              <select value={filter} onChange={(event) => setFilter(event.target.value)}>
                <option value="">All Types</option>
                {typeOptions.map(([type, count]) => (
                  <option key={type} value={type}>{type} ({count})</option>
                ))}
              </select>
              <button className="ghost" onClick={() => active?.id && loadGraph(active.id)}>
                <RefreshCw size={15} />
              </button>
              <button className="ghost" onClick={() => setFilter('')}>
                <Maximize2 size={15} />
              </button>
            </div>
          </div>
          <GraphCanvas graph={graph} selectedId={selectedId} onSelect={setSelectedId} filter={filter} search={search} />
        </section>
      </main>

      <aside className="right-rail">
        <Inspector selected={selected} active={active} onExpand={expandSelected} onRemove={removeSelected} />
        <EventHud events={events} />
      </aside>
    </div>
  );
}
