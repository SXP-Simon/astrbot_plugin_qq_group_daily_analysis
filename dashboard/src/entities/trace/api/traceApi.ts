import { apiGet, apiPost, extractData } from "../../../shared/api/bridge";
import { TraceRecord } from "../model/types";

export interface ListTracesParams {
  limit?: number;
  offset?: number;
  group_id?: string;
  status?: string;
  trigger_type?: string;
  search?: string;
  start_time?: number;
  end_time?: number;
  sort_by?: string;
  sort_order?: string;
  [key: string]: unknown;
}

// 内存不可变详情缓存 (最大 100 条 LRU 策略)
const MAX_CACHE_ENTRIES = 100;
const traceDetailCache = new Map<string, TraceRecord>();

export function invalidateTraceCache(traceId?: string): void {
  if (traceId) {
    traceDetailCache.delete(traceId);
  } else {
    traceDetailCache.clear();
  }
}

export async function fetchTraceList(
  params: ListTracesParams
): Promise<{ items: TraceRecord[]; total: number }> {
  const res = await apiGet<{ items: TraceRecord[]; total: number }>("traces", params);
  const data = extractData<{ items: TraceRecord[]; total: number }>(res);
  if (data && Array.isArray(data.items)) {
    return data;
  }
  return {
    items: [],
    total: 0,
  };
}

export async function fetchTraceDetail(
  traceId: string,
  forceRefresh = false
): Promise<TraceRecord | null> {
  // 1. 检查缓存命中（仅在未强制刷新且已存在缓存时）
  if (!forceRefresh && traceDetailCache.has(traceId)) {
    return traceDetailCache.get(traceId)!;
  }

  const res = await apiGet<TraceRecord>(`traces/${traceId}`);
  const data = extractData<TraceRecord>(res);

  // 2. 只有已终态（非 running）的不可变 Trace 才允许存入缓存，防止运行中阶段状态陈旧
  if (data && data.status !== "running") {
    if (traceDetailCache.size >= MAX_CACHE_ENTRIES) {
      const oldestKey = traceDetailCache.keys().next().value;
      if (oldestKey) traceDetailCache.delete(oldestKey);
    }
    traceDetailCache.set(traceId, data);
  } else if (data && data.status === "running") {
    // 若当前正在运行，务必清除缓存
    traceDetailCache.delete(traceId);
  }

  return data;
}

export interface LLMProviderItem {
  id: string;
  name: string;
  type?: string;
  label?: string;
}

export async function fetchProviderList(): Promise<LLMProviderItem[]> {
  const res = await apiGet<LLMProviderItem[]>("providers");
  const data = extractData<LLMProviderItem[]>(res);
  return Array.isArray(data) ? data : [];
}

export async function resumeTraceTask(
  traceId: string,
  providerId?: string,
  templateName?: string
): Promise<{ trace_id: string; message: string }> {
  const payload: Record<string, string> = {};
  if (providerId) payload.provider_id = providerId;
  if (templateName) payload.template_name = templateName;
  const res = await apiPost<{ trace_id: string; message: string }>(
    `tasks/${traceId}/resume`,
    payload
  );
  invalidateTraceCache(traceId);
  const data = extractData<{ trace_id: string; message: string }>(res);
  return data || { trace_id: traceId, message: "Task resume queued" };
}

