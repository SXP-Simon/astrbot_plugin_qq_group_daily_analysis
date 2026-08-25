import { apiGet, extractData } from "../../../shared/api/bridge";
import { ReportItem } from "../model/types";

export async function fetchReportHistory(): Promise<ReportItem[]> {
  const res = await apiGet<ReportItem[]>("reports/history");
  const data = extractData<ReportItem[]>(res);
  if (Array.isArray(data)) return data;
  return [];
}
