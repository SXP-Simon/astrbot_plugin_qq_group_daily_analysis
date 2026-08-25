import { apiGet } from "../../../shared/api/bridge";
import { GroupItem } from "../model/types";

let cachedGroups: GroupItem[] | null = null;

export function invalidateGroupsCache(): void {
  cachedGroups = null;
}

export async function fetchDistinctGroups(forceRefresh = false): Promise<GroupItem[]> {
  if (!forceRefresh && cachedGroups !== null) {
    return cachedGroups;
  }

  const res = await apiGet<GroupItem[]>("groups");
  let list: GroupItem[] = [];
  if (Array.isArray(res?.data)) {
    list = res.data;
  } else if (Array.isArray(res)) {
    list = res as unknown as GroupItem[];
  }

  cachedGroups = list;
  return list;
}
