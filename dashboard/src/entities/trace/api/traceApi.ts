import { apiGet, apiPost, extractData } from "@/shared/api/bridge";
import { z } from "zod";
import { TraceRecord } from "@/entities/trace/model/types";

export interface ListTracesParams {
  limit?: number;
  offset?: number;
  group_id?: string;
  platform?: string;
  status?: string;
  trigger_type?: string;
  search?: string;
  start_time?: number;
  end_time?: number;
  sort_by?: string;
  sort_order?: string;
  before_time?: number;
  before_id?: string;
  [key: string]: unknown;
}

// 内存不可变详情缓存 (最大 100 条 LRU 策略)
const MAX_CACHE_ENTRIES = 100;
const traceDetailCache = new Map<string, TraceRecord>();
const detailRequests = new Map<string, symbol>();
const TERMINAL_STATUSES = new Set<TraceRecord["status"]>([
  "succeeded",
  "completed",
  "warning",
  "failed",
  "aborted",
  "cancelled",
  "skipped",
]);

export function invalidateTraceCache(traceId?: string): void {
  if (traceId) {
    traceDetailCache.delete(traceId);
    detailRequests.delete(traceId);
  } else {
    traceDetailCache.clear();
    detailRequests.clear();
  }
}

export async function fetchTraceList(
  params: ListTracesParams,
): Promise<{ items: TraceRecord[]; total: number; has_more?: boolean }> {
  const res = await apiGet<{ items: TraceRecord[]; total: number; has_more?: boolean }>(
    "traces",
    params,
  );
  const data = extractData<{ items: TraceRecord[]; total: number; has_more?: boolean }>(res);
  if (data && Array.isArray(data.items)) {
    return data;
  }
  return {
    items: [],
    total: 0,
  };
}

export async function acknowledgeTrace(traceId: string, acknowledged: boolean) {
  const response = await apiPost<unknown>(`traces/${encodeURIComponent(traceId)}/acknowledgement`, {
    acknowledged,
  });
  const parsed = z
    .object({
      trace_id: z.literal(traceId),
      acknowledged_at: acknowledged ? z.number().positive() : z.null(),
    })
    .safeParse(extractData<unknown>(response));
  if (!parsed.success) throw new Error("知晓状态未能确认，请刷新后重试。");
  invalidateTraceCache(traceId);
  return parsed.data;
}

export async function fetchTraceDetail(
  traceId: string,
  forceRefresh = false,
): Promise<TraceRecord | null> {
  // 1. 检查缓存命中（仅在未强制刷新且已存在缓存时）
  if (!forceRefresh && traceDetailCache.has(traceId)) {
    const cached = traceDetailCache.get(traceId)!;
    traceDetailCache.delete(traceId);
    traceDetailCache.set(traceId, cached);
    return cached;
  }

  const request = Symbol(traceId);
  detailRequests.set(traceId, request);
  try {
    const res = await apiGet<TraceRecord>(`traces/${traceId}`);
    const data = extractData<TraceRecord>(res);

    // SSE 失效或较新请求出现后，迟到的响应不能重新写回旧缓存。
    if (detailRequests.get(traceId) !== request) return data;

    // 只有明确终态可缓存；pending、running 和未知状态都继续读取最新记录。
    if (data && TERMINAL_STATUSES.has(data.status)) {
      traceDetailCache.delete(traceId);
      if (traceDetailCache.size >= MAX_CACHE_ENTRIES) {
        const oldestKey = traceDetailCache.keys().next().value;
        if (oldestKey) traceDetailCache.delete(oldestKey);
      }
      traceDetailCache.set(traceId, data);
    } else {
      traceDetailCache.delete(traceId);
    }

    return data;
  } finally {
    if (detailRequests.get(traceId) === request) detailRequests.delete(traceId);
  }
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
  templateName?: string,
): Promise<{ trace_id: string; message: string }> {
  const payload: Record<string, string> = {};
  if (providerId) payload.provider_id = providerId;
  if (templateName) payload.template_name = templateName;
  const res = await apiPost<{ trace_id: string; message: string }>(
    `tasks/${traceId}/resume`,
    payload,
  );
  const parsed = z
    .object({
      trace_id: z.string().trim().min(1),
      message: z.string().optional(),
      status: z.enum(["ok", "success"]).optional(),
    })
    .safeParse(extractData<unknown>(res));
  if (!parsed.success) throw new Error("未收到有效的续跑回执，请刷新任务列表后确认。");
  invalidateTraceCache(traceId);
  return { trace_id: parsed.data.trace_id, message: parsed.data.message || "续跑任务已提交" };
}
