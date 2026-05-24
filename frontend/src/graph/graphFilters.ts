export function isGraphVisible(data: Record<string, unknown> | undefined): boolean {
  const visibility = String(data?.graph_visibility || "main_graph");
  return visibility === "main_graph";
}
