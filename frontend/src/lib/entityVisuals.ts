import { entityDefinitionFor } from "./entityTypes";

export function entityColorFor(type: string): string {
  return entityDefinitionFor(type)?.color || "#E0E0E3";
}

export function entityIconNameFor(type: string): string {
  return entityDefinitionFor(type)?.icon || "CircleDot";
}
