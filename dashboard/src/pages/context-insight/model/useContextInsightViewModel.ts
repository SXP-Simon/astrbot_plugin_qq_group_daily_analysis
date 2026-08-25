import { useEffect, useState } from "react";
import { fetchTraceList, fetchTraceDetail } from "../../../entities/trace/api/traceApi";
import { TraceRecord, ContextMetrics, TokenUsage } from "../../../entities/trace/model/types";

export function useContextInsightViewModel() {
  const [recentTraces, setRecentTraces] = useState<TraceRecord[]>([]);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [selectedTraceDetail, setSelectedTraceDetail] = useState<TraceRecord | null>(null);
  const [loading, setLoading] = useState(false);

  const loadRecentTraces = async () => {
    setLoading(true);
    try {
      const res = await fetchTraceList({ limit: 15, status: "succeeded" });
      setRecentTraces(res.items);
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
    loadRecentTraces();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (selectedTraceId) {
      fetchTraceDetail(selectedTraceId).then((detail) => {
        if (detail) setSelectedTraceDetail(detail);
      });
    } else {
      setSelectedTraceDetail(null);
    }
  }, [selectedTraceId]);

  const selectedSummary = recentTraces.find((t) => t.trace_id === selectedTraceId) || selectedTraceDetail;

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
    recentTraces,
    selectedTrace: selectedSummary,
    setSelectedTrace: (trace: TraceRecord | null) => setSelectedTraceId(trace?.trace_id || null),
    contextMetrics,
    tokenUsage,
    loading,
    refresh: () => {
      loadRecentTraces();
      if (selectedTraceId) {
        fetchTraceDetail(selectedTraceId, true).then((detail) => {
          if (detail) setSelectedTraceDetail(detail);
        });
      }
    },
  };
}
