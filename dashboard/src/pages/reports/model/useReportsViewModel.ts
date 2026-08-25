import { useEffect, useState } from "react";
import { message } from "antd";
import { fetchReportHistory, fetchReportContent } from "../../../entities/report/api/reportApi";
import { ReportItem } from "../../../entities/report/model/types";

export function useReportsViewModel() {
  const [reports, setReports] = useState<ReportItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [selectedReport, setSelectedReport] = useState<ReportItem | null>(null);

  const loadReports = async () => {
    setLoading(true);
    try {
      const list = await fetchReportHistory();
      setReports(list);
    } catch {
      // 忽略加载异常
    } finally {
      setLoading(false);
    }
  };

  const openPreview = async (report: ReportItem) => {
    setSelectedReport(report);
    setPreviewOpen(true);
    setPreviewLoading(true);
    try {
      const data = await fetchReportContent(report.filename);
      if (data && data.data_url) {
        setSelectedReport((prev) => ({
          ...(prev || report),
          ...data,
        }));
      } else {
        message.warning("未能读取到报告图片数据");
      }
    } catch {
      message.error("加载报告图片失败");
    } finally {
      setPreviewLoading(false);
    }
  };

  const closePreview = () => {
    setPreviewOpen(false);
    setSelectedReport(null);
  };

  const downloadReport = async (report: ReportItem) => {
    try {
      let dataUrl = report.data_url;
      if (!dataUrl) {
        const data = await fetchReportContent(report.filename);
        dataUrl = data?.data_url;
      }
      if (!dataUrl) {
        message.error("获取下载图片失败");
        return;
      }

      const a = document.createElement("a");
      a.href = dataUrl;
      a.download = report.filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      message.success(`已开始下载 ${report.filename}`);
    } catch {
      message.error("下载文件异常");
    }
  };

  useEffect(() => {
    loadReports();
  }, []);

  return {
    reports,
    loading,
    refresh: loadReports,
    previewOpen,
    previewLoading,
    selectedReport,
    openPreview,
    closePreview,
    downloadReport,
  };
}

