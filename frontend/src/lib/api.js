export async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    },
    ...options
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || body.error || `HTTP ${response.status}`);
  }
  return response.json();
}

export const createInvestigation = (target, mode) =>
  api('/api/investigations', {
    method: 'POST',
    body: JSON.stringify({ target, mode })
  });

export const listInvestigations = () => api('/api/investigations');
export const getInvestigation = (id) => api(`/api/investigations/${id}`);
export const getGraph = (id) => api(`/api/investigations/${id}/graph`);
export const getSchema = () => api('/api/schema');

export const expandEntity = (investigationId, entityId, mode) =>
  api(`/api/investigations/${investigationId}/expand`, {
    method: 'POST',
    body: JSON.stringify({ entity_id: entityId, mode })
  });

export const addEntity = (investigationId, payload) =>
  api(`/api/investigations/${investigationId}/entities`, {
    method: 'POST',
    body: JSON.stringify(payload)
  });

export const removeEntity = (investigationId, entityId) =>
  api(`/api/investigations/${investigationId}/entities/${entityId}`, {
    method: 'DELETE'
  });
