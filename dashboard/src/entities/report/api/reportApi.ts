import { apiGet, extractData } from "../../../shared/api/bridge";
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

