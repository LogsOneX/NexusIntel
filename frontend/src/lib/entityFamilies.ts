import { ENTITY_GROUPS, ENTITY_TYPES } from "./entityTypes";

export const ENTITY_FAMILIES = ENTITY_GROUPS;

export function entityTypesForFamily(family: string) {
  return ENTITY_TYPES.filter((item) => item.group === family);
}
