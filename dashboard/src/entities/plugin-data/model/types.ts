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
  description?: string;
  heat_score?: number;
  category?: string;
  keywords?: string[];
  [key: string]: unknown;
}

export interface ChatQualityDimension {
  name?: string;
  percentage?: number;
  comment?: string;
  color?: string;
}

export interface ChatQualityReviewObject {
  title?: string;
  subtitle?: string;
  dimensions?: ChatQualityDimension[];
  summary?: string;
}

export interface IncrementalBatchGoldenQuote {
  content?: string;
  text?: string;
  sender_nickname?: string;
  sender_name?: string;
  author?: string;
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
  golden_quotes?: IncrementalBatchGoldenQuote[];
  hourly_msg_counts?: Record<string, number>;
  hourly_char_counts?: Record<string, number>;
  token_usage?: {
    prompt_tokens?: number;
    completion_tokens?: number;
    total_tokens?: number;
    [key: string]: unknown;
  };
  chat_quality_review?: string | ChatQualityReviewObject | Record<string, unknown>;
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
  checkpoint_id?: string;
  group_id: string;
  date_str: string;
  stage_name: string;
  trace_id?: string;
  data_size_bytes?: number;
  data_size?: number;
  created_at?: number | string;
  created_at_formatted?: string;
  updated_at?: string;
  expire_at?: number;
  has_data?: boolean;
}

export interface CheckpointsListResponse {
  items: CheckpointItem[];
  total: number;
}

export interface CheckpointDetail {
  checkpoint_id?: string;
  group_id: string;
  date_str: string;
  stage_name: string;
  trace_id?: string;
  data?: unknown;
  checkpoint_data?: unknown;
  data_size_bytes?: number;
  data_size?: number;
  created_at?: number | string;
  created_at_formatted?: string;
  expire_at?: number;
}
