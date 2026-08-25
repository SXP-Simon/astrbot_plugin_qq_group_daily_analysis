import { useEffect, useState } from "react";
import { fetchTraceList, fetchTraceDetail } from "../../../entities/trace/api/traceApi";
import { fetchDistinctGroups } from "../../../entities/group/api/groupApi";
import { TraceRecord, ContextMetrics, TokenUsage } from "../../../entities/trace/model/types";
import { GroupItem } from "../../../entities/group/model/types";

export function useContextInsightViewModel() {
  const [traces, setTraces] = useState<TraceRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [selectedTraceDetail, setSelectedTraceDetail] = useState<TraceRecord | null>(null);
  const [loading, setLoading] = useState(false);

  // 筛选状态
  const [search, setSearch] = useState("");
  const [selectedGroup, setSelectedGroup] = useState<string | undefined>(undefined);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [dateRange, setDateRange] = useState<[number, number] | null>(null);
  const [groups, setGroups] = useState<GroupItem[]>([]);

  const loadGroups = async () => {
    try {
      const gList = await fetchDistinctGroups();
      setGroups(gList);
    } catch {
      // 忽略群组加载异常
    }
  };

  const loadTraces = async () => {
    setLoading(true);
    try {
      const res = await fetchTraceList({
        limit: 200,
        group_id: selectedGroup || undefined,
        search: search.trim() || undefined,
        status: statusFilter || undefined,
        start_time: dateRange ? dateRange[0] : undefined,
        end_time: dateRange ? dateRange[1] : undefined,
        sort_by: "started_at",
        sort_order: "desc",
      });
      setTraces(res.items);
      setTotal(res.total);

      if (res.items.length > 0) {
        if (!selectedTraceId || !res.items.some((t) => t.trace_id === selectedTraceId)) {
          setSelectedTraceId(res.items[0].trace_id);
        }
      } else {
        setSelectedTraceId(null);
        setSelectedTraceDetail(null);
      }
    } catch (e) {
      // 忽略加载异常
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadGroups();
  }, []);

  useEffect(() => {
    loadTraces();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, selectedGroup, statusFilter, dateRange]);

  useEffect(() => {
    if (selectedTraceId) {
      fetchTraceDetail(selectedTraceId).then((detail) => {
        if (detail) setSelectedTraceDetail(detail);
      });
    } else {
      setSelectedTraceDetail(null);
    }
  }, [selectedTraceId]);

  const selectedSummary = traces.find((t) => t.trace_id === selectedTraceId) || selectedTraceDetail;

  const defaultContextMetrics: ContextMetrics = {
    trace_id: selectedTraceId || "",
    raw_message_count: selectedSummary?.raw_message_count ?? 0,
    cleaned_message_count: selectedSummary?.cleaned_message_count ?? 0,
    compression_ratio: selectedSummary?.compression_ratio ?? 0,
    incremental_batches: 0,
    window_size: selectedSummary?.raw_message_count ?? 0,
  };

  const defaultTokenUsage: TokenUsage = {
    trace_id: selectedTraceId || "",
    prompt_tokens: 0,
    completion_tokens: 0,
    total_tokens: selectedSummary?.total_tokens ?? 0,
    estimated_cost: selectedSummary?.estimated_cost ?? 0,
    per_analyzer: {},
  };

  const contextMetrics = selectedTraceDetail?.context_metrics || defaultContextMetrics;
  const tokenUsage = selectedTraceDetail?.token_usage || defaultTokenUsage;

  return {
    traces,
    total,
    selectedTrace: selectedSummary,
    setSelectedTrace: (trace: TraceRecord | null) => setSelectedTraceId(trace?.trace_id || null),
    contextMetrics,
    tokenUsage,
    loading,
    search,
    selectedGroup,
    statusFilter,
    dateRange,
    groups,
    setSearch,
    setSelectedGroup,
    setStatusFilter,
    setDateRange,
    refresh: () => {
      loadTraces();
      if (selectedTraceId) {
        fetchTraceDetail(selectedTraceId, true).then((detail) => {
          if (detail) setSelectedTraceDetail(detail);
        });
      }
    },
  };
}
