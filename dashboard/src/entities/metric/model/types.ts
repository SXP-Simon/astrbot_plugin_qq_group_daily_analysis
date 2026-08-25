export interface MetricsSummary {
  total_traces: number;
  succeeded_count: number;
  failed_count: number;
  success_rate: number;
  avg_duration_ms: number;
  today_traces: number;
  today_active_groups: number;
  total_tokens_spent: number;
  total_cost_spent: number;
  today_tokens_spent: number;
  today_cost_spent: number;
}
