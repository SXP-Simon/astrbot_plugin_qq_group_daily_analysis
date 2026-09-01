import { apiGet, extractData } from "../../../shared/api/bridge";
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
  const data = extractData<GroupItem[]>(res);
  const list: GroupItem[] = Array.isArray(data) ? data : [];

  cachedGroups = list;
  return list;
}
