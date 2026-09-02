/**
 * 静态资源与存储可观测性类型定义 (符合 DASHBOARD_UI_STYLE_GUIDE.md)
 */

export interface ResourceCacheItem {
  url: string;
  hash: string;
  template: string;
  category: "fonts" | "css" | "images" | "scripts" | string;
  mime_type: string;
  size: number;
  size_formatted?: string;
  file_path: string;
  relative_path?: string;
  created_at?: number;
  last_accessed_at?: number;
  access_count: number;
  exists?: boolean;
}

export interface ResourceCacheStats {
  total_files: number;
  total_bytes: number;
  total_access_count: number;
  by_category: {
    fonts: { files: number; bytes: number };
    css: { files: number; bytes: number };
    images: { files: number; bytes: number };
    scripts: { files: number; bytes: number };
    [key: string]: { files: number; bytes: number };
  };
  by_template: Record<
    string,
    {
      files: number;
      bytes: number;
      access_count: number;
      categories: Record<string, number>;
    }
  >;
}

export interface StorageOverview {
  root_path: string;
  total: {
    files: number;
    bytes: number;
    mb: number;
  };
  database: {
    traces_sqlite_bytes: number;
    traces_sqlite_mb: number;
    history_db_bytes: number;
    history_db_mb?: number;
  };
  resources_cache: {
    files: number;
    bytes: number;
    mb: number;
    stats?: ResourceCacheStats;
  };
  reports: {
    files: number;
    bytes: number;
    mb: number;
  };
  avatars: {
    files: number;
    bytes: number;
    mb: number;
  };
  checkpoints: {
    files: number;
    bytes: number;
    mb: number;
  };
}

export interface ResourceLocalizationItem {
  url: string;
  type: string;
  mime: string;
  size: number;
  cached: boolean;
  source: string;
}

export interface ResourceLocalizationTelemetry {
  template: string;
  started_at?: number;
  total_intercepted: number;
  cache_hits: number;
  downloaded: number;
  local_asset_hits: number;
  failed: number;
  inlined_bytes: number;
  duration_ms: number;
  hit_rate: number;
  preconnect_tags_stripped?: number;
  items: ResourceLocalizationItem[];
}
