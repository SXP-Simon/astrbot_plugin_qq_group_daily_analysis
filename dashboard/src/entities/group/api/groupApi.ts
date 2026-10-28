import { apiGet, extractData } from "../../../shared/api/bridge";
import { z } from "zod";
import { groupItemSchema, type GroupItem } from "../model/types";

let cachedGroups: GroupItem[] | null = null;

export function invalidateGroupsCache(): void {
  cachedGroups = null;
}

export async function fetchDistinctGroups(forceRefresh = false): Promise<GroupItem[]> {
  if (!forceRefresh && cachedGroups !== null) {
    return cachedGroups;
  }

  const res = await apiGet<unknown>("groups");
  const parsed = z.array(groupItemSchema).safeParse(extractData<unknown>(res));
  if (!parsed.success) throw new Error("群列表格式不正确，请刷新页面或检查插件版本。");
  const list = parsed.data;

  cachedGroups = list;
  return list;
}
