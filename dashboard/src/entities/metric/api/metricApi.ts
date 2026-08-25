import { apiGet } from "../../../shared/api/bridge";
import { MetricsSummary } from "../model/types";

export async function fetchMetricsSummary(): Promise<MetricsSummary> {
  const res = await apiGet<MetricsSummary>("metrics/summary");
  if (res?.data && typeof res.data === "object") {
    return res.data as MetricsSummary;
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
