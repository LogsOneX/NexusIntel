export type TransformAction = { id: string; label: string; description: string };

export function upperSnake(value: string): string {
  const normalized = value.replace(/([a-z0-9])([A-Z])/g, "$1_$2").replace(/[^A-Za-z0-9]+/g, "_").replace(/^_+|_+$/g, "");
  return (normalized || "RELATED_TO").toUpperCase();
}

export function transformTerminology(id: string): string {
  return id.replace("ghost_identity", "public_identity_resolution").replace("deep_sweep", "extended_profile_sweep").replaceAll("_", " ");
}
