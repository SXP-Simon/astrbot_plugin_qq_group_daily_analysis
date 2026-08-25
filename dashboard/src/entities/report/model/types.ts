export interface ReportItem {
  filename: string;
  size_bytes: number;
  modified_at: number;
  absolute_path?: string;
  data_url?: string;
  is_html?: boolean;
  html_content?: string;
  group_id?: string;
  group_name?: string;
  platform?: string;
  trace_id?: string;
}

