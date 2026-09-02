/**
 * 静态资源与存储可观测性 API 客户端
 */

import { apiGet, apiPost } from "../../../shared/api/bridge";
import {
  ResourceCacheItem,
  ResourceCacheStats,
  StorageOverview,
} from "../model/types";

export interface TemplateOption {
  id: string;
  label: string;
  is_custom?: boolean;
}

export interface ResourceCacheResponse {
  stats: ResourceCacheStats;
  resources: ResourceCacheItem[];
  available_templates?: TemplateOption[];
}

export async function fetchReportTemplates(): Promise<TemplateOption[]> {
  const res = await apiGet<TemplateOption[]>("templates");
  if (res && res.data && Array.isArray(res.data)) {
    return res.data;
  }
  return [];
}


export async function fetchResourceCache(
  template?: string,
  category?: string
): Promise<ResourceCacheResponse | null> {
  const params: Record<string, unknown> = {};
  if (template && template !== "all") params.template = template;
  if (category && category !== "all") params.category = category;

  const res = await apiGet<ResourceCacheResponse>(
    "resources/cache",
    params
  );
  if (res && res.data) {
    return res.data;
  }
  return null;
}

export async function clearResourceCache(
  template?: string,
  category?: string
): Promise<{ deleted_files: number; freed_bytes: number; freed_mb: number } | null> {
  const body: Record<string, unknown> = {};
  if (template && template !== "all") body.template = template;
  if (category && category !== "all") body.category = category;

  const res = await apiPost<{
    deleted_files: number;
    freed_bytes: number;
    freed_mb: number;
  }>("resources/cache/clear", body);
  if (res && res.data) {
    return res.data;
  }
  return null;
}

export async function triggerResourcePrefetch(
  template?: string
): Promise<{
  success: boolean;
  message: string;
  duration_ms?: number;
  data?: any;
}> {
  const body: Record<string, unknown> = {};
  if (template && template !== "all") {
    body.template = template;
  }
  const res = await apiPost<{
    template?: string;
    duration_ms?: number;
    total_duration_ms?: number;
  }>("resources/prefetch", body);
  if (res && res.status === "ok") {
    const dur =
      (res.data as any)?.duration_ms || (res.data as any)?.total_duration_ms;
    return {
      success: true,
      message: res.message || "预取完成",
      duration_ms: dur,
      data: res.data,
    };
  }
  return {
    success: false,
    message: res?.message || "预取失败",
  };
}


export async function fetchStorageOverview(): Promise<StorageOverview | null> {
  const res = await apiGet<StorageOverview>("storage/overview");
  if (res && res.data) {
    return res.data;
  }
  return null;
}
