import { useEffect, useState } from "react";
import { z } from "zod";
import { fetchAnalyticsTrends } from "../../../entities/metric/api/metricApi";
import type { AnalyticsTrendsResponse } from "../../../entities/metric/model/types";

export const TREND_RANGES = [
  { value: "48h", label: "近48小时", granularity: "hour", count: 48 },
  { value: "7d", label: "近7天", granularity: "day", count: 7 },
  { value: "14d", label: "近14天", granularity: "day", count: 14 },
  { value: "30d", label: "近30天", granularity: "day", count: 30 },
] as const;
type Range = (typeof TREND_RANGES)[number]["value"];
const count = z.number().nonnegative();
const breakdown = z.object({ name: z.string(), total_tokens: count, request_count: count });
const trendsSchema: z.ZodType<AnalyticsTrendsResponse> = z.object({
  granularity: z.enum(["day", "hour"]),
  range_count: z.number().int().positive(),
  points: z.array(
    z.object({
      date: z.string(),
      date_full: z.string(),
      timestamp: z.number(),
      request_count: count,
      succeeded_count: count,
      failed_count: count,
      prompt_tokens: count,
      completion_tokens: count,
      total_tokens: count,
      estimated_cost: count,
    }),
  ),
  provider_breakdown: z.array(breakdown),
  model_breakdown: z.array(breakdown),
});

export function useOverviewTrends(initialTrends?: AnalyticsTrendsResponse) {
  const [range, setRange] = useState<Range>("14d");
  const [displayed, setDisplayed] = useState<{
    range: Range;
    data: AnalyticsTrendsResponse;
  } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refreshVersion, setRefreshVersion] = useState(0);
  const seed = range === "14d" ? initialTrends : undefined;

  useEffect(() => {
    let active = true;
    const definition = TREND_RANGES.find((item) => item.value === range)!;
    const initial = trendsSchema.safeParse(seed);
    if (
      !refreshVersion &&
      initial.success &&
      initial.data.granularity === definition.granularity &&
      initial.data.range_count === definition.count
    ) {
      setDisplayed({ range, data: initial.data });
      setLoading(false);
      setError("");
      return;
    }
    setLoading(true);
    setError("");
    void fetchAnalyticsTrends(definition.granularity, definition.count)
      .then((response) => {
        if (!active) return;
        const parsed = trendsSchema.safeParse(response);
        if (
          !parsed.success ||
          parsed.data.granularity !== definition.granularity ||
          parsed.data.range_count !== definition.count
        ) {
          setError("趋势数据不完整或时间范围不符，请重新加载。");
          return;
        }
        setDisplayed({ range, data: parsed.data });
      })
      .catch(() => {
        if (active) setError("趋势暂时无法读取，请检查连接后重试。");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [range, seed, refreshVersion]);

  const points = displayed?.data.points ?? [];
  const providers = [...(displayed?.data.provider_breakdown ?? [])]
    .filter((item) => item.total_tokens > 0 || item.request_count > 0)
    .sort((a, b) => b.total_tokens - a.total_tokens);
  const providerChart =
    providers.length <= 7
      ? providers
      : [
          ...providers.slice(0, 6),
          {
            name: `其他服务商（${providers.length - 6}个）`,
            total_tokens: providers.slice(6).reduce((sum, item) => sum + item.total_tokens, 0),
            request_count: providers.slice(6).reduce((sum, item) => sum + item.request_count, 0),
          },
        ];
  return {
    range,
    displayedRange: displayed?.range,
    loading,
    error,
    points,
    providers,
    providerChart,
    totalRequests: points.reduce((sum, item) => sum + item.request_count, 0),
    totalTokens: points.reduce((sum, item) => sum + item.total_tokens, 0),
    selectRange: (value: string) => {
      const item = TREND_RANGES.find((item) => item.value === value);
      if (item) setRange(item.value);
    },
    refresh: () => setRefreshVersion((version) => version + 1),
  };
}
