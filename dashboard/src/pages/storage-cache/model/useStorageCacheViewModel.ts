import { useCallback, useEffect, useState } from "react";
import { message } from "antd";
import {
  clearResourceCache,
  fetchResourceCache,
  fetchStorageOverview,
  triggerResourcePrefetch,
} from "../../../entities/resource/api/resourceApi";
import {
  ResourceCacheItem,
  ResourceCacheStats,
  StorageOverview,
} from "../../../entities/resource/model/types";

export function useStorageCacheViewModel() {
  const [storage, setStorage] = useState<StorageOverview | null>(null);
  const [stats, setStats] = useState<ResourceCacheStats | null>(null);
  const [resources, setResources] = useState<ResourceCacheItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [prefetching, setPrefetching] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<string>("all");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const refresh = useCallback(
    async (isManual = false) => {
      if (!isManual) setLoading(true);
      try {
        const [storageRes, cacheRes] = await Promise.allSettled([
          fetchStorageOverview(),
          fetchResourceCache(
            selectedTemplate === "all" ? undefined : selectedTemplate,
            selectedCategory === "all" ? undefined : selectedCategory
          ),
        ]);

        if (storageRes.status === "fulfilled" && storageRes.value) {
          setStorage(storageRes.value);
        }
        if (cacheRes.status === "fulfilled" && cacheRes.value) {
          setStats(cacheRes.value.stats);
          setResources(cacheRes.value.resources || []);
        }
      } catch (err) {
        if (isManual) message.error(`刷新存储指标失败: ${err}`);
      } finally {
        if (!isManual) setLoading(false);
      }
    },
    [selectedTemplate, selectedCategory]
  );

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handlePrefetch = async () => {
    setPrefetching(true);
    try {
      const ok = await triggerResourcePrefetch();
      if (ok) {
        message.success("已在后台触发模板静态资源与字体全量预取！");
        setTimeout(() => refresh(true), 1500);
      } else {
        message.error("触发预取失败");
      }
    } catch (err) {
      message.error(`预取请求异常: ${err}`);
    } finally {
      setPrefetching(false);
    }
  };

  const handleClear = async (template?: string, category?: string) => {
    setClearing(true);
    try {
      const res = await clearResourceCache(
        template ?? (selectedTemplate === "all" ? undefined : selectedTemplate),
        category ?? (selectedCategory === "all" ? undefined : selectedCategory)
      );
      if (res) {
        message.success(
          `清理完成！已删除 ${res.deleted_files} 个文件，释放 ${res.freed_mb} MB 磁盘空间`
        );
        refresh(true);
      }
    } catch (err) {
      message.error(`清理缓存异常: ${err}`);
    } finally {
      setClearing(false);
    }
  };

  const availableTemplates = Object.keys(stats?.by_template || {});

  const filteredResources = resources.filter((item) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      item.url?.toLowerCase().includes(query) ||
      item.template?.toLowerCase().includes(query) ||
      item.category?.toLowerCase().includes(query) ||
      item.mime_type?.toLowerCase().includes(query) ||
      item.file_path?.toLowerCase().includes(query)
    );
  });

  return {
    storage,
    stats,
    resources: filteredResources,
    allResourcesCount: resources.length,
    loading,
    prefetching,
    clearing,
    selectedTemplate,
    setSelectedTemplate,
    selectedCategory,
    setSelectedCategory,
    searchQuery,
    setSearchQuery,
    availableTemplates,
    refresh,
    handlePrefetch,
    handleClear,
  };
}
