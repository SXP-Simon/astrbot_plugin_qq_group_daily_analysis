import { useEffect, useState } from "react";
import { fetchReportHistory } from "../../../entities/report/api/reportApi";
import { ReportItem } from "../../../entities/report/model/types";

export function useReportsViewModel() {
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(false);

  const loadReports = async () => {
    setLoading(true);
    try {
      const list = await fetchReportHistory();
      setReports(list);
    } catch (e) {
      // 忽略加载异常
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReports();
  }, []);

  return {
    reports,
    loading,
    refresh: loadReports,
  };
}
