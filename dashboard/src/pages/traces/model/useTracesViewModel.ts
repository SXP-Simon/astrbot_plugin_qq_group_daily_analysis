import { useEffect, useRef, useState } from "react";
import { fetchTraceList } from "@/entities/trace/api/traceApi";
import { fetchGroupSessions } from "@/entities/group/api/groupApi";
import type { TraceRecord } from "@/entities/trace/model/types";
import type { GroupItem } from "@/entities/group/model/types";
import type { TraceQuery, TraceSortField } from "@/entities/trace/model/traceQuery";

const INITIAL_QUERY: TraceQuery = {
  page: 1,
  pageSize: 15,
  search: "",
  dateRange: null,
  sortField: "started_at",
  sortOrder: "desc",
};

export function useTracesViewModel() {
  const [query, setQuery] = useState<TraceQuery>(INITIAL_QUERY);
  const [traces, setTraces] = useState<TraceRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [hasUpdates, setHasUpdates] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [groupsError, setGroupsError] = useState("");
  const [refreshRequest, setRefreshRequest] = useState({ version: 0, silent: false });
  const previousQuery = useRef<TraceQuery | null>(null);

  useEffect(() => {
    let active = true;
    setGroupsError("");
    void fetchGroupSessions()
      .then((result) => {
        if (active) setGroups(result);
      })
      .catch((reason: unknown) => {
        if (active)
          setGroupsError(
            reason instanceof Error
              ? `群聊列表加载失败：${reason.message}`
              : "群聊列表加载失败，仍可使用搜索筛选。",
          );
      });
    return () => {
      active = false;
    };
  }, [refreshRequest.version]);

  useEffect(() => {
    let active = true;
    const delay = previousQuery.current && previousQuery.current.search !== query.search ? 250 : 0;
    const silent = previousQuery.current === query && refreshRequest.silent;
    previousQuery.current = query;
    setLoading(!silent);
    setError("");
    const timer = setTimeout(async () => {
      try {
        const result = await fetchTraceList({
          limit: query.pageSize,
          offset: (query.page - 1) * query.pageSize,
          group_id: query.selectedGroup || undefined,
          platform: query.selectedPlatform,
          search: query.search.trim() || undefined,
          status: query.statusFilter || undefined,
          trigger_type: query.triggerTypeFilter || undefined,
          start_time: query.dateRange?.[0],
          end_time: query.dateRange?.[1],
          sort_by: query.sortField,
          sort_order: query.sortOrder,
        });
        if (!active) return;
        const lastPage = Math.max(1, Math.ceil(result.total / query.pageSize));
        if (query.page > lastPage) {
          setQuery((current) => ({ ...current, page: lastPage }));
          return;
        }
        setTraces(result.items);
        setTotal(result.total);
      } catch (reason) {
        if (active)
          setError(
            reason instanceof Error
              ? `分析记录加载失败：${reason.message}`
              : "分析记录加载失败，请重试。",
          );
      } finally {
        if (active) setLoading(false);
      }
    }, delay);
    // 筛选变化立即废弃旧请求，即使新搜索仍在防抖等待中。
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query, refreshRequest]);

  return {
    ...query,
    traces,
    hasUpdates,
    markUpdated: () => setHasUpdates(true),
    total,
    loading,
    error,
    groups,
    groupsError,
    setSearch: (search: string) => setQuery((current) => ({ ...current, search, page: 1 })),
    setStatusFilter: (statusFilter?: string) =>
      setQuery((current) => ({ ...current, statusFilter, page: 1 })),
    setTriggerTypeFilter: (triggerTypeFilter?: string) =>
      setQuery((current) => ({ ...current, triggerTypeFilter, page: 1 })),
    setSelectedPlatform: (selectedPlatform?: string) =>
      setQuery((current) => ({ ...current, selectedPlatform, selectedGroup: undefined, page: 1 })),
    setSelectedGroup: (selectedGroup?: string, platform?: string) =>
      setQuery((current) => ({
        ...current,
        selectedPlatform: platform ?? current.selectedPlatform,
        selectedGroup,
        page: 1,
      })),
    setDateRange: (dateRange: [number, number] | null) =>
      setQuery((current) => ({ ...current, dateRange, page: 1 })),
    resetFilters: () =>
      setQuery((current) => ({
        ...INITIAL_QUERY,
        pageSize: current.pageSize,
        sortField: current.sortField,
        sortOrder: current.sortOrder,
      })),
    changePage: (page: number, pageSize: number) =>
      setQuery((current) => ({ ...current, page, pageSize })),
    changeSort: (field: TraceSortField) =>
      setQuery((current) => ({
        ...current,
        page: 1,
        sortField: field,
        sortOrder: current.sortField === field && current.sortOrder === "desc" ? "asc" : "desc",
      })),
    refresh: (silent = true) => {
      setHasUpdates(false);
      setRefreshRequest((current) => ({ version: current.version + 1, silent }));
    },
  };
}
