/**
 * 静态资源与存储可观测性 API 客户端
 */

import { apiGet, apiPost } from "../../../shared/api/bridge";
import {
  ResourceCacheItem,
  ResourceCacheStats,
  StorageOverview,
} from "../model/types";

export interface ResourceCacheResponse {
  stats: ResourceCacheStats;
  resources: ResourceCacheItem[];
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

export async function triggerResourcePrefetch(): Promise<boolean> {
  const res = await apiPost("resources/prefetch", {});
  return !!res && res.status === "ok";
}

export async function fetchStorageOverview(): Promise<StorageOverview | null> {
  const res = await apiGet<StorageOverview>("storage/overview");
  if (res && res.data) {
    return res.data;
  }
  return null;
}
