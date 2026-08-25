export interface ReportItem {
  filename: string;
  size_bytes: number;
  modified_at: number;
  absolute_path?: string;
  data_url?: string;
  group_id?: string;
  group_name?: string;
}

