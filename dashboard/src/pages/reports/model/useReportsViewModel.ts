import { useEffect, useMemo, useRef, useState } from "react";
import { fetchReportHistory } from "../../../entities/report/api/reportApi";
import { fetchDistinctGroups } from "../../../entities/group/api/groupApi";
import type { ReportItem } from "../../../entities/report/model/types";
import type { GroupItem } from "../../../entities/group/model/types";
import { useReportActions } from "./useReportActions";

interface ReportQuery {
  page: number;
  pageSize: number;
  search: string;
  selectedGroup?: string;
}
const INITIAL_QUERY: ReportQuery = { page: 1, pageSize: 20, search: "" };

export function useReportsViewModel() {
  const [query, setQuery] = useState<ReportQuery>(INITIAL_QUERY);
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loadedPage, setLoadedPage] = useState(1);
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [groupsError, setGroupsError] = useState("");
  const [dateRange, setDateRange] = useState<[number, number] | null>(null);
  const [sortOrder, setSortOrder] = useState<"desc" | "asc">("desc");
  const [refreshRequest, setRefreshRequest] = useState({ version: 0, silent: false });
  const previousQuery = useRef<ReportQuery | null>(null);
  const reportActions = useReportActions();

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
          search: query.search.trim() || undefined,
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

  // 接口按时间倒序分页；日期过滤与反向排列只作用于已载入这一页，界面明确此范围。
  const filteredReports = useMemo(
    () =>
      reports
        .filter((report) => {
          if (!dateRange) return true;
          const time = report.modified_at ?? report.created_at;
          return typeof time === "number" && time >= dateRange[0] && time <= dateRange[1];
        })
        .sort((a, b) => {
          const first = a.modified_at ?? a.created_at ?? 0;
          const second = b.modified_at ?? b.created_at ?? 0;
          return sortOrder === "desc" ? second - first : first - second;
        }),
    [reports, dateRange, sortOrder],
  );

  const mergedGroups = useMemo(() => {
    const map = new Map(groups.map((group) => [group.group_id, group]));
    for (const report of reports) {
      if (report.group_id && !map.has(report.group_id))
        map.set(report.group_id, {
          group_id: report.group_id,
          group_name: report.group_name || `群 ${report.group_id}`,
          platform: report.platform || "",
        });
    }
    return [...map.values()];
  }, [groups, reports]);

  return {
    ...query,
    reports: filteredReports,
    rawReports: reports,
    groups: mergedGroups,
    loading,
    error,
    groupsError,
    loadedPage,
    dateRange,
    setDateRange,
    sortOrder,
    setSortOrder,
    total,
    setSearch: (search: string) => setQuery((current) => ({ ...current, search, page: 1 })),
    setSelectedGroup: (selectedGroup?: string) =>
      setQuery((current) => ({ ...current, selectedGroup, page: 1 })),
    resetFilters: () => {
      setQuery((current) => ({ ...INITIAL_QUERY, pageSize: current.pageSize }));
      setDateRange(null);
    },
    handlePageChange: (page: number, pageSize?: number) =>
      setQuery((current) => ({
        ...current,
        page,
        pageSize: pageSize ?? current.pageSize,
      })),
    refresh: (silent = true, resetPage = false) => {
      if (resetPage) setQuery((current) => ({ ...current, page: 1 }));
      setRefreshRequest((current) => ({ version: current.version + 1, silent }));
    },
    ...reportActions,
  };
}
