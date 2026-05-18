import cytoscape from 'cytoscape';
import { useEffect, useMemo, useRef } from 'react';

const palette = {
  target: '#f8fafc',
  username: '#38bdf8',
  email: '#22c55e',
  domain: '#f59e0b',
  website: '#f97316',
  url: '#eab308',
  ip: '#a78bfa',
  service: '#14b8a6',
  social_profile: '#60a5fa',
  developer_profile: '#34d399',
  creator_profile: '#fb7185',
  identity_profile: '#c084fc',
  package_profile: '#4ade80',
  risk: '#ef4444',
  task: '#94a3b8',
  signal: '#facc15',
  tracker: '#f43f5e',
  organization: '#2dd4bf'
};

function nodeColor(type) {
  return palette[type] || '#8b9bb4';
}

export default function GraphCanvas({ graph, selectedId, onSelect, filter, search }) {
  const containerRef = useRef(null);
  const cyRef = useRef(null);

  const elements = useMemo(() => {
    const query = (search || '').trim().toLowerCase();
    const allowedNodes = new Set(
      (graph.nodes || [])
        .filter((node) => !filter || node.type === filter)
        .filter((node) => !query || `${node.label} ${node.value} ${node.type}`.toLowerCase().includes(query))
        .map((node) => node.id)
    );
    return [
      ...(graph.nodes || [])
        .filter((node) => allowedNodes.has(node.id))
        .map((node) => ({
          data: {
            id: node.id,
            label: node.label || node.value,
            type: node.type,
            confidence: node.confidence,
            source: node.source
          }
        })),
      ...(graph.edges || [])
        .filter((edge) => allowedNodes.has(edge.source) && allowedNodes.has(edge.target))
        .map((edge) => ({
          data: {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            label: edge.label,
            type: edge.type,
            confidence: edge.confidence
          }
        }))
    ];
  }, [graph, filter, search]);

  useEffect(() => {
    if (!containerRef.current) return;
    const cy = cytoscape({
      container: containerRef.current,
      elements: [],
      minZoom: 0.18,
      maxZoom: 3,
      wheelSensitivity: 0.18,
      style: [
        {
          selector: 'node',
          style: {
            'background-color': (ele) => nodeColor(ele.data('type')),
            'border-color': '#e5e7eb',
            'border-opacity': 0.22,
            'border-width': 1,
            color: '#e5eefb',
            label: 'data(label)',
            'font-family': 'Inter, ui-sans-serif, system-ui',
            'font-size': 10,
            'text-wrap': 'wrap',
            'text-max-width': 110,
            'text-valign': 'bottom',
            'text-margin-y': 8,
            width: (ele) => Math.max(30, Math.min(76, 28 + ele.data('confidence') / 2)),
            height: (ele) => Math.max(30, Math.min(76, 28 + ele.data('confidence') / 2)),
            'overlay-opacity': 0
          }
        },
        {
          selector: 'edge',
          style: {
            width: (ele) => Math.max(1, ele.data('confidence') / 28),
            'line-color': '#334155',
            'target-arrow-color': '#475569',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            opacity: 0.72,
            label: 'data(label)',
            color: '#93a4b8',
            'font-size': 8,
            'text-rotation': 'autorotate',
            'text-background-color': '#071016',
            'text-background-opacity': 0.75,
            'text-background-padding': 2
          }
        },
        {
          selector: 'node:selected',
          style: {
            'border-width': 3,
            'border-color': '#ffffff'
          }
        }
      ],
      layout: { name: 'cose', animate: false, fit: true, padding: 48, nodeRepulsion: 9000, idealEdgeLength: 130 }
    });
    cy.on('tap', 'node', (event) => onSelect(event.target.id()));
    cy.on('tap', (event) => {
      if (event.target === cy) onSelect(null);
    });
    cyRef.current = cy;
    return () => cy.destroy();
  }, [onSelect]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.elements().remove();
    cy.add(elements);
    cy.layout({ name: 'cose', animate: false, fit: true, padding: 52, nodeRepulsion: 10000, idealEdgeLength: 132 }).run();
  }, [elements]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy) return;
    cy.nodes().unselect();
    if (selectedId) cy.getElementById(selectedId).select();
  }, [selectedId]);

  return <div className="graph-canvas" ref={containerRef} />;
}
