import { apiGet, apiPost, extractData } from "../../../shared/api/bridge";
import { PluginLogItem, PluginLogResponse } from "../model/types";

export interface LogFilterParams {
  limit?: number;
  offset?: number;
  level?: string;
  trace_id?: string;
  tag?: string;
  search?: string;
}

export async function fetchPluginLogs(
  params?: LogFilterParams
): Promise<PluginLogResponse> {
  const query: Record<string, string | number> = {};
  if (params?.limit !== undefined) query.limit = params.limit;
  if (params?.offset !== undefined) query.offset = params.offset;
  if (params?.level) query.level = params.level;
  if (params?.trace_id) query.trace_id = params.trace_id;
  if (params?.tag) query.tag = params.tag;
  if (params?.search) query.search = params.search;

  const res = await apiGet<PluginLogResponse>("logs", query);
  const data = extractData<PluginLogResponse>(res);
  return data || { items: [], total: 0, available_tags: [] };
}

export async function fetchTraceLogs(
  traceId: string
): Promise<PluginLogItem[]> {
  const res = await apiGet<PluginLogItem[]>(`traces/${traceId}/logs`);
  const data = extractData<PluginLogItem[]>(res);
  return Array.isArray(data) ? data : [];
}

export async function clearPluginLogs(): Promise<void> {
  await apiPost("logs/clear");
}
