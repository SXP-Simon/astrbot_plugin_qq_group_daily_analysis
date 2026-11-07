import { useEffect, useRef, useState } from "react";
import { fetchTraceList, fetchTraceDetail } from "../../../entities/trace/api/traceApi";
import { fetchDistinctGroups } from "../../../entities/group/api/groupApi";
import type { TraceRecord, ContextMetrics } from "../../../entities/trace/model/types";
import type { GroupItem } from "../../../entities/group/model/types";

interface InsightFilters {
  search: string;
  selectedGroup?: string;
  statusFilter?: string;
  dateRange: [number, number] | null;
}
const INITIAL_FILTERS: InsightFilters = { search: "", dateRange: null };

export function useContextInsightViewModel() {
  const [filters, setFilters] = useState<InsightFilters>(INITIAL_FILTERS);
  const [traces, setTraces] = useState<TraceRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [detail, setDetail] = useState<TraceRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");
  const [detailError, setDetailError] = useState("");
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [groupsError, setGroupsError] = useState("");
  const [refreshRequest, setRefreshRequest] = useState({ version: 0, silent: false });
  const previousFilters = useRef<InsightFilters | null>(null);
  const detailVersion = useRef(0);
  const listGeneration = useRef(0);
  const moreRequest = useRef<symbol | null>(null);
  const [nextCursor, setNextCursor] = useState<{ time: number; id: string } | null>(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [moreError, setMoreError] = useState("");
  const [hasUpdates, setHasUpdates] = useState(false);

  useEffect(() => {
    let active = true;
    setGroupsError("");
    void fetchDistinctGroups()
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
    const delay =
      previousFilters.current && previousFilters.current.search !== filters.search ? 250 : 0;
    const filtersChanged = previousFilters.current !== filters;
    const silent = !filtersChanged && refreshRequest.silent;
    listGeneration.current += 1;
    moreRequest.current = null;
    setLoadingMore(false);
    setMoreError("");
    previousFilters.current = filters;
    setLoading(!silent);
    setError("");
    const timer = setTimeout(async () => {
      try {
        const result = await fetchTraceList({
          limit: 50,
          group_id: filters.selectedGroup || undefined,
          search: filters.search.trim() || undefined,
          status: filters.statusFilter || undefined,
          start_time: filters.dateRange?.[0],
          end_time: filters.dateRange?.[1],
          sort_by: "started_at",
          sort_order: "desc",
        });
        if (!active) return;
        setTraces(result.items);
        setTotal(result.total);
        const last = result.items.at(-1);
        setNextCursor(
          (result.has_more ?? result.items.length === 50) && last
            ? { time: last.started_at, id: last.trace_id }
            : null,
        );
        // 主动刷新后不悄悄改选其他任务；筛选条件变化才重新选择第一条。
        setSelectedTraceId((current) =>
          result.items.some((trace) => trace.trace_id === current)
            ? current
            : filtersChanged || !current
              ? (result.items[0]?.trace_id ?? null)
              : current,
        );
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
    // 输入变化立即废弃旧请求，搜索等待期间也不接收旧结果。
    return () => {
      active = false;
      clearTimeout(timer);
      listGeneration.current += 1;
      moreRequest.current = null;
    };
  }, [filters, refreshRequest]);

  useEffect(() => {
    let active = true;
    const forceRefresh = detailVersion.current !== refreshRequest.version;
    detailVersion.current = refreshRequest.version;
    setDetailError("");
    setDetailLoading(Boolean(selectedTraceId));
    if (!selectedTraceId) {
      setDetail(null);
      return;
    }
    void fetchTraceDetail(selectedTraceId, forceRefresh)
      .then((result) => {
        if (!active) return;
        if (result && result.trace_id !== selectedTraceId)
          throw new Error("返回的任务编号不一致，请刷新后重试。");
        setDetail(result);
        if (!result) setDetailError("未找到这项任务的详情，以下仅显示已读取的概要。");
      })
      .catch((reason: unknown) => {
        if (active)
          setDetailError(
            reason instanceof Error
              ? `任务详情加载失败：${reason.message}`
              : "任务详情加载失败，请重试。",
          );
      })
      .finally(() => {
        if (active) setDetailLoading(false);
      });
    return () => {
      active = false;
    };
  }, [selectedTraceId, refreshRequest.version]);

  const loadMore = async () => {
    if (loading || moreRequest.current || !nextCursor) return;
    const generation = listGeneration.current;
    const request = Symbol("older-traces");
    moreRequest.current = request;
    setLoadingMore(true);
    setMoreError("");
    try {
      const result = await fetchTraceList({
        limit: 50,
        group_id: filters.selectedGroup || undefined,
        search: filters.search.trim() || undefined,
        status: filters.statusFilter || undefined,
        start_time: filters.dateRange?.[0],
        end_time: filters.dateRange?.[1],
        sort_by: "started_at",
        sort_order: "desc",
        before_time: nextCursor.time,
        before_id: nextCursor.id,
      });
      if (generation !== listGeneration.current || moreRequest.current !== request) return;
      setTraces((current) => {
        const ids = new Set(current.map((trace) => trace.trace_id));
        return [...current, ...result.items.filter((trace) => !ids.has(trace.trace_id))];
      });
      const last = result.items.at(-1);
      setNextCursor(
        (result.has_more ?? result.items.length === 50) && last
          ? { time: last.started_at, id: last.trace_id }
          : null,
      );
    } catch {
      if (generation === listGeneration.current && moreRequest.current === request)
        setMoreError("更早的记录读取失败，请重试。已加载的记录会保留。");
    } finally {
      if (moreRequest.current === request) {
        moreRequest.current = null;
        setLoadingMore(false);
      }
    }
  };

  // 选择变化后的首次渲染也不能借用上一项的明细，更不能把缺失字段补成零。
  const currentDetail = detail?.trace_id === selectedTraceId ? detail : null;
  const selectedTrace = traces.find((trace) => trace.trace_id === selectedTraceId) ?? null;
  const contextMetrics: Partial<ContextMetrics> = currentDetail?.context_metrics ?? {
    trace_id: selectedTraceId ?? "",
    raw_message_count: selectedTrace?.raw_message_count ?? undefined,
    cleaned_message_count: selectedTrace?.cleaned_message_count ?? undefined,
    compression_ratio: selectedTrace?.compression_ratio ?? undefined,
  };

  return {
    ...filters,
    traces,
    total,
    hasUpdates,
    markUpdated: () => setHasUpdates(true),
    hasMore: nextCursor !== null,
    loadingMore,
    moreError,
    loadMore,
    selectionMissing: Boolean(selectedTraceId && !selectedTrace && !loading),
    selectedTrace,
    contextMetrics,
    tokenUsage: currentDetail?.token_usage ?? null,
    loading,
    detailLoading,
    error,
    detailError,
    groups,
    groupsError,
    setSelectedTrace: (trace: TraceRecord | null) => setSelectedTraceId(trace?.trace_id ?? null),
    setSearch: (search: string) => setFilters((current) => ({ ...current, search })),
    setSelectedGroup: (selectedGroup?: string) =>
      setFilters((current) => ({ ...current, selectedGroup })),
    setStatusFilter: (statusFilter?: string) =>
      setFilters((current) => ({ ...current, statusFilter })),
    setDateRange: (dateRange: [number, number] | null) =>
      setFilters((current) => ({ ...current, dateRange })),
    resetFilters: () => setFilters(INITIAL_FILTERS),
    refresh: (silent = true) => {
      setHasUpdates(false);
      setRefreshRequest((current) => ({ version: current.version + 1, silent }));
    },
  };
}
