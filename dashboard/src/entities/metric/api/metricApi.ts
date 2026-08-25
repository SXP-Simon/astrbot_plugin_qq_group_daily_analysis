import { apiGet, extractData } from "../../../shared/api/bridge";
import { MetricsSummary } from "../model/types";

export async function fetchMetricsSummary(): Promise<MetricsSummary> {
  const res = await apiGet<MetricsSummary>("metrics/summary");
  const data = extractData<MetricsSummary>(res);
  if (data && typeof data === "object") {
    return {
      total_traces: data.total_traces ?? 0,
      succeeded_count: data.succeeded_count ?? 0,
      failed_count: data.failed_count ?? 0,
      success_rate: data.success_rate ?? 0,
      avg_duration_ms: data.avg_duration_ms ?? 0,
      today_traces: data.today_traces ?? 0,
      today_active_groups: data.today_active_groups ?? 0,
      total_tokens_spent: data.total_tokens_spent ?? 0,
      total_cost_spent: data.total_cost_spent ?? 0,
      today_tokens_spent: data.today_tokens_spent ?? 0,
      today_cost_spent: data.today_cost_spent ?? 0,
    };
  }
  return {
    total_traces: 0,
    succeeded_count: 0,
    failed_count: 0,
    success_rate: 0,
    avg_duration_ms: 0,
    today_traces: 0,
    today_active_groups: 0,
    total_tokens_spent: 0,
    total_cost_spent: 0,
    today_tokens_spent: 0,
    today_cost_spent: 0,
  };
}
