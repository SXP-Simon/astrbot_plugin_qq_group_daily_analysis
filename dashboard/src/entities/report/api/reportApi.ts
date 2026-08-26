import { apiGet, apiPost, extractData } from "../../../shared/api/bridge";
import { ReportItem } from "../model/types";

export async function fetchReportHistory(): Promise<ReportItem[]> {
  const res = await apiGet<ReportItem[]>("reports/history");
  const data = extractData<ReportItem[]>(res);
  if (Array.isArray(data)) return data;
  return [];
}

export async function fetchReportContent(filename: string): Promise<ReportItem | null> {
  const res = await apiGet<ReportItem>("reports/content", { filename });
  const data = extractData<ReportItem>(res);
  return data || null;
}

export async function rerenderReport(params: {
  group_id: string;
  date_str?: string;
  template_name?: string;
  render_format?: "image" | "html";
  platform_id?: string;
  trace_id?: string;
}): Promise<{ success: boolean; filename: string; report_path: string; is_html: boolean } | null> {
  const res = await apiPost<{ success: boolean; filename: string; report_path: string; is_html: boolean }>(
    "reports/rerender",
    params
  );
  return extractData(res) || null;
}

