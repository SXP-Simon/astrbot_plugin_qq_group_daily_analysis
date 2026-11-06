import type { MetricsSummary, AnalyticsTrendsResponse } from "../../entities/metric/model/types";

const now = new Date();
const today = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();
const dayCounts = [
  3, 0, 4, 2, 5, 1, 2, 0, 3, 1, 4, 6, 2, 3, 4, 5, 1, 2, 3, 4, 6, 5, 7, 9, 8, 6, 7, 7, 14, 18,
];
let ordinal = 0;
// 各范围共用一组确定性示例事件，切换小时与日期时总数和服务商消耗仍可对照。
const events = dayCounts.flatMap((count, index) => {
  const day = new Date(today);
  day.setDate(day.getDate() - (dayCounts.length - 1 - index));
  const available = index === dayCounts.length - 1 ? now.getTime() - today : 86400000;
  return Array.from({ length: count }, (_, slot) => {
    ordinal += 1;
    return {
      timestamp: (day.getTime() + Math.floor((available * (slot + 1)) / (count + 1))) / 1000,
      failed: ordinal % 20 === 0,
      provider: ordinal % 3 === 0 ? "示例 OpenAI" : "示例 DeepSeek",
      model: ordinal % 3 === 0 ? "gpt-4o" : "deepseek-chat",
      prompt: 1600,
      completion: 750,
    };
  });
});

export function createMockAnalyticsTrends(
  granularity: "day" | "hour" = "day",
  rangeCount = 14,
): AnalyticsTrendsResponse {
  const count = Number.isFinite(rangeCount)
    ? Math.max(1, Math.min(Math.floor(rangeCount), granularity === "hour" ? 168 : 90))
    : 14;
  const current = new Date(now);
  if (granularity === "hour") current.setMinutes(0, 0, 0);
  else current.setHours(0, 0, 0, 0);
  const interval = granularity === "hour" ? 3600 : 86400;
  const start = current.getTime() / 1000 - (count - 1) * interval;
  const selected = events.filter(
    (event) => event.timestamp >= start && event.timestamp <= now.getTime() / 1000,
  );
  const points = Array.from({ length: count }, (_, index) => {
    const timestamp = start + index * interval;
    const date = new Date(timestamp * 1000);
    const hour = String(date.getHours()).padStart(2, "0");
    const fullDate = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    const bucket = selected.filter(
      (event) => event.timestamp >= timestamp && event.timestamp < timestamp + interval,
    );
    const prompt = bucket.reduce((sum, event) => sum + event.prompt, 0);
    const completion = bucket.reduce((sum, event) => sum + event.completion, 0);
    return {
      date: `${date.getMonth() + 1}/${date.getDate()}${granularity === "hour" ? ` ${hour}:00` : ""}`,
      date_full: `${fullDate}${granularity === "hour" ? ` ${hour}:00` : ""}`,
      timestamp,
      request_count: bucket.length,
      succeeded_count: bucket.filter((event) => !event.failed).length,
      failed_count: bucket.filter((event) => event.failed).length,
      prompt_tokens: prompt,
      completion_tokens: completion,
      total_tokens: prompt + completion,
      estimated_cost: Number(((prompt + completion) * 0.000002).toFixed(4)),
    };
  });
  const providers = new Map<
    string,
    { name: string; total_tokens: number; request_count: number }
  >();
  const models = new Map<string, { name: string; total_tokens: number; request_count: number }>();
  for (const event of selected) {
    for (const [map, name] of [
      [providers, event.provider],
      [models, event.model],
    ] as const) {
      const item = map.get(name) ?? { name, total_tokens: 0, request_count: 0 };
      item.total_tokens += event.prompt + event.completion;
      item.request_count += 1;
      map.set(name, item);
    }
  }
  return {
    granularity,
    range_count: count,
    points,
    provider_breakdown: [...providers.values()],
    model_breakdown: [...models.values()],
  };
}

export const mockAnalyticsTrends = createMockAnalyticsTrends();
const monthly = createMockAnalyticsTrends("day", 30);
const latest = monthly.points.at(-1)!;
const succeeded = events.filter((event) => !event.failed).length;
export const mockMetricsSummary: MetricsSummary = {
  total_traces: events.length,
  succeeded_count: succeeded,
  failed_count: events.length - succeeded,
  success_rate: Math.round((succeeded / events.length) * 1000) / 10,
  avg_duration_ms: 12450,
  today_traces: latest.request_count,
  today_active_groups: 6,
  total_tokens_spent: monthly.points.reduce((sum, point) => sum + point.total_tokens, 0),
  total_cost_spent: Number(
    monthly.points.reduce((sum, point) => sum + point.estimated_cost, 0).toFixed(4),
  ),
  today_tokens_spent: latest.total_tokens,
  today_cost_spent: latest.estimated_cost,
  trends: mockAnalyticsTrends,
};
