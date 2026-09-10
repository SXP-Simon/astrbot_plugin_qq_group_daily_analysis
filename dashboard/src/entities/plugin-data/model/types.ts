export interface SectionStats {
  count: number;
  size_bytes: number;
}

export interface PluginDataOverview {
  avatars: SectionStats;
  custom_templates: SectionStats;
  config_files: SectionStats;
  config_backups: SectionStats;
  reports: SectionStats;
  temp_files: SectionStats;
}

export interface IncrementalBatchTopic {
  title?: string;
  summary?: string;
  heat_score?: number;
  keywords?: string[];
  [key: string]: unknown;
}

export interface IncrementalBatchItem {
  group_id: string;
  batch_id: string;
  timestamp: number;
  created_at_iso?: string;
  messages_count: number;
  characters_count: number;
  topics_count: number;
  topics?: IncrementalBatchTopic[];
  golden_quotes_count?: number;
  golden_quotes?: unknown[];
  hourly_msg_counts?: Record<string, number>;
  hourly_char_counts?: Record<string, number>;
  token_usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
    [key: string]: unknown;
  };
  chat_quality_review?: string;
  last_message_timestamp?: number;
  participant_ids?: string[];
  [key: string]: unknown;
}

export interface IncrementalCursorInfo {
  group_id: string;
  last_analyzed_timestamp: number;
  last_message_timestamp: number;
  tracked_message_ids_count: number;
}

export interface IncrementalBatchesResponse {
  group_id: string;
  cursor: IncrementalCursorInfo;
  batches: IncrementalBatchItem[];
}

export interface CheckpointItem {
  group_id: string;
  date_str: string;
  stage_name: string;
  data_size_bytes?: number;
  created_at?: string;
  updated_at?: string;
  has_data?: boolean;
}

export interface CheckpointsListResponse {
  items: CheckpointItem[];
  total: number;
}

export interface CheckpointDetail {
  group_id: string;
  date_str: string;
  stage_name: string;
  data: unknown;
  created_at?: string;
  updated_at?: string;
}
