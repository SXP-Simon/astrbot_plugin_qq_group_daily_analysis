export interface AnalyticsTrendPoint {
  date: string;
  date_full: string;
  timestamp: number;
  request_count: number;
  succeeded_count: number;
  failed_count: number;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost: number;
}

export interface ProviderBreakdownItem {
  name: string;
  total_tokens: number;
  request_count: number;
}

export interface ModelBreakdownItem {
  name: string;
  total_tokens: number;
  request_count: number;
}

export interface AnalyticsTrendsResponse {
  granularity: "day" | "hour";
  range_count: number;
  points: AnalyticsTrendPoint[];
  provider_breakdown: ProviderBreakdownItem[];
  model_breakdown: ModelBreakdownItem[];
}

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
  trends?: AnalyticsTrendsResponse;
}
