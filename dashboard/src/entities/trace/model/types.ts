export interface TraceSpan {
  span_id: string;
  trace_id: string;
  stage_name: string;
  status: string;
  started_at: number;
  duration_ms: number;
  payload: Record<string, unknown>;
}

export interface ContextMetrics {
  trace_id: string;
  raw_message_count: number;
  cleaned_message_count: number;
  compression_ratio: number;
  incremental_batches: number;
  window_size: number;
}

export interface TokenUsage {
  trace_id: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  estimated_cost: number;
  per_analyzer: Record<string, { prompt_tokens: number; completion_tokens: number; total_tokens: number }>;
}

export interface TraceRecord {
  trace_id: string;
  group_id: string;
  group_name: string;
  platform: string;
  trigger_type: string;
  status: "running" | "succeeded" | "failed" | "aborted";
  started_at: number;
  completed_at?: number;
  duration_ms?: number;
  error_stage?: string;
  error_message?: string;
  stack_trace?: string;
  extra?: Record<string, unknown>;
  total_tokens?: number;
  estimated_cost?: number;
  raw_message_count?: number;
  cleaned_message_count?: number;
  compression_ratio?: number;
  spans?: TraceSpan[];
  context_metrics?: ContextMetrics | null;
  token_usage?: TokenUsage | null;
  current_stage?: string;
  report_files?: Array<{
    filename: string;
    path?: string;
    format?: string;
    report_type?: string;
    size_bytes?: number;
    created_at?: number;
  }>;
}
