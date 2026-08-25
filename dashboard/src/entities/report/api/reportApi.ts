import { apiGet } from "../../../shared/api/bridge";
import { ReportItem } from "../model/types";

export async function fetchReportHistory(): Promise<ReportItem[]> {
  const res = await apiGet<ReportItem[]>("reports/history");
  if (Array.isArray(res?.data)) return res.data;
  if (Array.isArray(res)) return res as unknown as ReportItem[];
  return [];
}
