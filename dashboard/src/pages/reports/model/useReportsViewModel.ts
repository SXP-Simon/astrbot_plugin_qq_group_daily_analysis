import { useEffect, useMemo, useRef, useState } from "react";
import { fetchReportHistory, type ReportKind } from "../../../entities/report/api/reportApi";
import { fetchGroupSessions } from "../../../entities/group/api/groupApi";
import type { ReportItem } from "../../../entities/report/model/types";
import type { GroupItem } from "../../../entities/group/model/types";
import { useReportActions } from "./useReportActions";

interface ReportQuery {
  page: number;
  pageSize: number;
  search: string;
  selectedGroup?: string;
  selectedPlatform?: string;
  reportType?: ReportKind;
  dateRange: [number, number] | null;
  sortOrder: "desc" | "asc";
}
const INITIAL_QUERY: ReportQuery = {
  page: 1,
  pageSize: 20,
  search: "",
  dateRange: null,
  sortOrder: "desc",
};

export function useReportsViewModel() {
  const [query, setQuery] = useState<ReportQuery>(INITIAL_QUERY);
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loadedPage, setLoadedPage] = useState(1);
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [groupsError, setGroupsError] = useState("");
  const [hasUpdates, setHasUpdates] = useState(false);
  const [refreshRequest, setRefreshRequest] = useState({ version: 0, silent: false });
  const previousQuery = useRef<ReportQuery | null>(null);
  const reportActions = useReportActions();

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
              : "群聊列表加载失败，仍可搜索报告。",
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
        const result = await fetchReportHistory({
          limit: query.pageSize,
          offset: (query.page - 1) * query.pageSize,
          group_id: query.selectedGroup || undefined,
          platform: query.selectedPlatform,
          search: query.search.trim() || undefined,
          start_time: query.dateRange?.[0],
          end_time: query.dateRange?.[1],
          sort_order: query.sortOrder,
          ...(query.reportType ? { report_type: query.reportType } : {}),
        });
        if (!active) return;
        const lastPage = Math.max(1, Math.ceil(result.total / query.pageSize));
        if (query.page > lastPage) {
          setQuery((current) => ({ ...current, page: lastPage }));
          return;
        }
        setReports(result.items);
        setTotal(result.total);
        setLoadedPage(query.page);
      } catch (reason) {
        if (active)
          setError(
            reason instanceof Error
              ? `报告列表加载失败：${reason.message}`
              : "报告列表加载失败，请重试。",
          );
      } finally {
        if (active) setLoading(false);
      }
    }, delay);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [query, refreshRequest]);

  const mergedGroups = useMemo(() => {
    const map = new Map(
      groups.map((group) => [JSON.stringify([group.platform, group.group_id]), group]),
    );
    for (const report of reports) {
      if (report.group_id && !map.has(JSON.stringify([report.platform || "", report.group_id])))
        map.set(JSON.stringify([report.platform || "", report.group_id]), {
          group_id: report.group_id,
          group_name: report.group_name || `群 ${report.group_id}`,
          platform: report.platform || "",
        });
    }
    return [...map.values()];
  }, [groups, reports]);

  return {
    ...query,
    reports,
    rawReports: reports,
    groups: mergedGroups,
    loading,
    error,
    groupsError,
    loadedPage,
    hasUpdates,
    markUpdated: () => setHasUpdates(true),
    setDateRange: (dateRange: [number, number] | null) =>
      setQuery((current) => ({ ...current, dateRange, page: 1 })),
    setSortOrder: (sortOrder: "desc" | "asc") =>
      setQuery((current) => ({ ...current, sortOrder, page: 1 })),
    total,
    setReportType: (reportType?: ReportKind) =>
      setQuery((current) => ({ ...current, reportType, page: 1 })),
    setSearch: (search: string) => setQuery((current) => ({ ...current, search, page: 1 })),
    setSelectedPlatform: (selectedPlatform?: string) =>
      setQuery((current) => ({ ...current, selectedPlatform, selectedGroup: undefined, page: 1 })),
    setSelectedGroup: (selectedGroup?: string, platform?: string) =>
      setQuery((current) => ({
        ...current,
        selectedPlatform: platform ?? current.selectedPlatform,
        selectedGroup,
        page: 1,
      })),
    resetFilters: () => {
      setQuery((current) => ({ ...INITIAL_QUERY, pageSize: current.pageSize }));
    },
    handlePageChange: (page: number, pageSize?: number) =>
      setQuery((current) => ({
        ...current,
        page,
        pageSize: pageSize ?? current.pageSize,
      })),
    refresh: (silent = true, resetPage = false) => {
      setHasUpdates(false);
      if (resetPage) setQuery((current) => ({ ...current, page: 1 }));
      setRefreshRequest((current) => ({ version: current.version + 1, silent }));
    },
    ...reportActions,
  };
}
