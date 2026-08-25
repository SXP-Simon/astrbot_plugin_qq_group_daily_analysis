import { useEffect, useState } from "react";
import type { TablePaginationConfig } from "antd/es/table";
import type { FilterValue, SorterResult } from "antd/es/table/interface";
import { fetchTraceList } from "../../../entities/trace/api/traceApi";
import { fetchDistinctGroups } from "../../../entities/group/api/groupApi";
import { TraceRecord } from "../../../entities/trace/model/types";
import { GroupItem } from "../../../entities/group/model/types";

export function useTracesViewModel() {
  const [traces, setTraces] = useState<TraceRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(15);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [selectedGroup, setSelectedGroup] = useState<string | undefined>(undefined);
  const [dateRange, setDateRange] = useState<[number, number] | null>(null);
  const [sortField, setSortField] = useState<string>("started_at");
  const [sortOrder, setSortOrder] = useState<string>("desc");
  const [groups, setGroups] = useState<GroupItem[]>([]);

  const loadGroups = async () => {
    try {
      const gList = await fetchDistinctGroups();
      setGroups(gList);
    } catch {
      // 忽略群组加载异常
    }
  };

  const loadData = async (
    currentPage = page,
    currentSize = pageSize,
    currentSortField = sortField,
    currentSortOrder = sortOrder
  ) => {
    setLoading(true);
    try {
      const res = await fetchTraceList({
        limit: currentSize,
        offset: (currentPage - 1) * currentSize,
        group_id: selectedGroup || undefined,
        search: search.trim() || undefined,
        status: statusFilter || undefined,
        start_time: dateRange ? dateRange[0] : undefined,
        end_time: dateRange ? dateRange[1] : undefined,
        sort_by: currentSortField,
        sort_order: currentSortOrder,
      });
      setTraces(res.items);
      setTotal(res.total);
    } catch {
      // 忽略加载异常
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGroups();
  }, []);

  useEffect(() => {
    loadData(1, pageSize, sortField, sortOrder);
    setPage(1);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, statusFilter, selectedGroup, dateRange, sortField, sortOrder]);

  const handleTableChange = (
    pagination: TablePaginationConfig,
    _filters: Record<string, FilterValue | null>,
    sorter: SorterResult<TraceRecord> | SorterResult<TraceRecord>[]
  ) => {
    let newSortField = "started_at";
    let newSortOrder = "desc";

    const singleSorter = Array.isArray(sorter) ? sorter[0] : sorter;
    if (singleSorter && singleSorter.field) {
      newSortField = String(singleSorter.field);
      newSortOrder = singleSorter.order === "ascend" ? "asc" : "desc";
    }

    setSortField(newSortField);
    setSortOrder(newSortOrder);

    if (pagination.current && pagination.pageSize) {
      setPage(pagination.current);
      setPageSize(pagination.pageSize);
      loadData(pagination.current, pagination.pageSize, newSortField, newSortOrder);
    }
  };

  return {
    traces,
    total,
    loading,
    page,
    pageSize,
    search,
    setSearch,
    statusFilter,
    setStatusFilter,
    selectedGroup,
    setSelectedGroup,
    dateRange,
    setDateRange,
    groups,
    handleTableChange,
    refresh: () => loadData(page, pageSize, sortField, sortOrder),
  };
}
