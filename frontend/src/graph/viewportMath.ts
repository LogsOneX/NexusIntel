export type ViewportPoint = { x: number; y: number };
export type ViewportRect = { left: number; top: number; width: number; height: number };

export function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function screenToWorld(clientX: number, clientY: number, rect: ViewportRect, pan: ViewportPoint, zoom: number): ViewportPoint {
  return {
    x: (clientX - rect.left - pan.x) / zoom,
    y: (clientY - rect.top - pan.y) / zoom,
  };
}

export function worldToScreen(x: number, y: number, pan: ViewportPoint, zoom: number): ViewportPoint {
  return {
    x: x * zoom + pan.x,
    y: y * zoom + pan.y,
  };
}

export function zoomToCursor(params: { clientX: number; clientY: number; rect: ViewportRect; pan: ViewportPoint; zoom: number; nextZoom: number }): { pan: ViewportPoint; zoom: number } {
  const mouseX = params.clientX - params.rect.left;
  const mouseY = params.clientY - params.rect.top;
  const worldX = (mouseX - params.pan.x) / params.zoom;
  const worldY = (mouseY - params.pan.y) / params.zoom;
  return {
    zoom: params.nextZoom,
    pan: {
      x: mouseX - worldX * params.nextZoom,
      y: mouseY - worldY * params.nextZoom,
    },
  };
}

export function fitBoundsToViewport(params: { positions: ViewportPoint[]; rect: Pick<ViewportRect, "width" | "height">; nodeWidth: number; nodeHeight: number; padding?: number; minZoom?: number; maxZoom?: number }): { pan: ViewportPoint; zoom: number } {
  const padding = params.padding ?? 120;
  const minZoom = params.minZoom ?? 0.25;
  const maxZoom = params.maxZoom ?? 2.5;
  if (!params.positions.length || params.rect.width <= 0 || params.rect.height <= 0) return { pan: { x: 0, y: 0 }, zoom: 1 };
  const minX = Math.min(...params.positions.map((item) => item.x));
  const minY = Math.min(...params.positions.map((item) => item.y));
  const maxX = Math.max(...params.positions.map((item) => item.x + params.nodeWidth));
  const maxY = Math.max(...params.positions.map((item) => item.y + params.nodeHeight));
  const boundsWidth = Math.max(1, maxX - minX);
  const boundsHeight = Math.max(1, maxY - minY);
  const usableWidth = Math.max(1, params.rect.width - padding * 2);
  const usableHeight = Math.max(1, params.rect.height - padding * 2);
  const zoom = clamp(Math.min(usableWidth / boundsWidth, usableHeight / boundsHeight), minZoom, maxZoom);
  const centerX = minX + boundsWidth / 2;
  const centerY = minY + boundsHeight / 2;
  return {
    zoom,
    pan: {
      x: params.rect.width / 2 - centerX * zoom,
      y: params.rect.height / 2 - centerY * zoom,
    },
  };
}
