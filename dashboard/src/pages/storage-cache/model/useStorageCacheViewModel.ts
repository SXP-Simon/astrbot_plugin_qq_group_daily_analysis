import { useCallback, useEffect, useRef, useState } from "react";
import { message } from "antd";
import {
  clearResourceCache,
  fetchReportTemplates,
  fetchResourceCache,
  fetchStorageOverview,
  TemplateOption,
  triggerResourcePrefetch,
} from "../../../entities/resource/api/resourceApi";
import {
  ResourceCacheItem,
  ResourceCacheStats,
  StorageOverview,
} from "../../../entities/resource/model/types";

export interface PrefetchProgressState {
  active: boolean;
  templateName?: string;
  startTime?: number;
  elapsedSeconds: number;
}

export function useStorageCacheViewModel() {
  const [storage, setStorage] = useState<StorageOverview | null>(null);
  const [stats, setStats] = useState<ResourceCacheStats | null>(null);
  const [resources, setResources] = useState<ResourceCacheItem[]>([]);
  const [availableTemplates, setAvailableTemplates] = useState<
    TemplateOption[]
  >([]);
  const [loading, setLoading] = useState(false);
  const [prefetchProgress, setPrefetchProgress] =
    useState<PrefetchProgressState>({
      active: false,
      elapsedSeconds: 0,
    });
  const [clearing, setClearing] = useState(false);
  const [selectedTemplate, setSelectedTemplate] = useState<string>("all");
  const [selectedCategory, setSelectedCategory] = useState<string>("all");
  const [searchQuery, setSearchQuery] = useState<string>("");

  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);


  const refresh = useCallback(
    async (isManual = false) => {
      if (!isManual) setLoading(true);
      try {
        const [storageRes, cacheRes, tplRes] = await Promise.allSettled([
          fetchStorageOverview(),
          fetchResourceCache(
            selectedTemplate === "all" ? undefined : selectedTemplate,
            selectedCategory === "all" ? undefined : selectedCategory
          ),
          fetchReportTemplates(),
        ]);

        if (storageRes.status === "fulfilled" && storageRes.value) {
          setStorage(storageRes.value);
        }
        if (cacheRes.status === "fulfilled" && cacheRes.value) {
          setStats(cacheRes.value.stats);
          setResources(cacheRes.value.resources || []);
          if (
            cacheRes.value.available_templates &&
            cacheRes.value.available_templates.length > 0
          ) {
            setAvailableTemplates(cacheRes.value.available_templates);
          }
        }
        if (
          tplRes.status === "fulfilled" &&
          tplRes.value &&
          tplRes.value.length > 0
        ) {
          setAvailableTemplates((prev) => (prev.length > 0 ? prev : tplRes.value));
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

  // 预取计时器
  useEffect(() => {
    if (prefetchProgress.active) {
      timerRef.current = setInterval(() => {
        setPrefetchProgress((prev) => ({
          ...prev,
          elapsedSeconds: prev.elapsedSeconds + 1,
        }));
      }, 1000);
    } else {
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [prefetchProgress.active]);

  const handlePrefetch = async (targetTemplate?: string) => {
    const tmpl =
      targetTemplate ||
      (selectedTemplate === "all" ? undefined : selectedTemplate);
    const isAll = !tmpl || tmpl === "all";

    // 查找用户友好的模板名称
    const matched = availableTemplates.find((t) => t.id === tmpl);
    const displayTitle = isAll
      ? "全部模板"
      : matched
      ? matched.label
      : `模板 [${tmpl}]`;

    setPrefetchProgress({
      active: true,
      templateName: displayTitle,
      startTime: Date.now(),
      elapsedSeconds: 0,
    });

    try {
      const res = await triggerResourcePrefetch(tmpl);
      if (res.success) {
        const durStr = res.duration_ms
          ? ` (总耗时 ${(res.duration_ms / 1000).toFixed(1)}s)`
          : "";
        message.success(`${displayTitle} 静态资源与字体预取完成！${durStr}`);
        await refresh(true);
      } else {
        message.error(`预取失败: ${res.message}`);
      }
    } catch (err) {
      message.error(`预取请求异常: ${err}`);
    } finally {
      setPrefetchProgress({
        active: false,
        elapsedSeconds: 0,
      });
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
    prefetchProgress,
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
