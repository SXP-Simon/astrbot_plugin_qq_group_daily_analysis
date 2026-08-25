import { useEffect, useState } from "react";
import { fetchTraceList } from "../../../entities/trace/api/traceApi";
import { TraceRecord, ContextMetrics, TokenUsage } from "../../../entities/trace/model/types";

export function useContextInsightViewModel() {
  const [recentTraces, setRecentTraces] = useState<TraceRecord[]>([]);
  const [selectedTrace, setSelectedTrace] = useState<TraceRecord | null>(null);
  const [loading, setLoading] = useState(false);

  const loadRecentTraces = async () => {
    setLoading(true);
    try {
      const res = await fetchTraceList({ limit: 15, status: "succeeded" });
      setRecentTraces(res.items);
      if (res.items.length > 0 && !selectedTrace) {
        setSelectedTrace(res.items[0]);
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

  const defaultContextMetrics: ContextMetrics = {
    trace_id: selectedTrace?.trace_id || "",
    raw_message_count: 2400,
    cleaned_message_count: 1350,
    compression_ratio: 0.56,
    incremental_batches: 3,
    window_size: 2400,
  };

  const defaultTokenUsage: TokenUsage = {
    trace_id: selectedTrace?.trace_id || "",
    prompt_tokens: 8200,
    completion_tokens: 1800,
    total_tokens: 10000,
    estimated_cost: 0.015,
    per_analyzer: {
      topics: { prompt_tokens: 2800, completion_tokens: 600, total_tokens: 3400 },
      user_titles: { prompt_tokens: 2300, completion_tokens: 500, total_tokens: 2800 },
      golden_quotes: { prompt_tokens: 1300, completion_tokens: 300, total_tokens: 1600 },
      comic_storyboard: { prompt_tokens: 1800, completion_tokens: 400, total_tokens: 2200 },
    },
  };

  const contextMetrics = selectedTrace?.context_metrics || defaultContextMetrics;
  const tokenUsage = selectedTrace?.token_usage || defaultTokenUsage;

  return {
    recentTraces,
    selectedTrace,
    setSelectedTrace,
    contextMetrics,
    tokenUsage,
    loading,
    refresh: loadRecentTraces,
  };
}
