import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { fetchReportContent } from "@/entities/report/api/reportApi";
import type { ReportItem } from "@/entities/report/model/types";

export function useReportActions() {
  const epoch = useRef(0);
  const previewRequest = useRef(0);
  const downloads = useRef(new Set<string>());
  const blobUrls = useRef(new Map<string, number>());
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState("");
  const [selectedReport, setSelectedReport] = useState<ReportItem | null>(null);
  const [downloadingFiles, setDownloadingFiles] = useState<ReadonlySet<string>>(new Set());
  const [downloadFailure, setDownloadFailure] = useState<{
    filename: string;
    message: string;
  } | null>(null);

  useEffect(() => {
    const pending = epoch;
    const urls = blobUrls.current;
    const locks = downloads.current;
    return () => {
      pending.current++;
      locks.clear();
      for (const [url, timer] of urls) {
        clearTimeout(timer);
        URL.revokeObjectURL(url);
      }
      urls.clear();
    };
  }, []);

  const openPreview = async (report: ReportItem) => {
    const generation = epoch.current;
    const request = ++previewRequest.current;
    setSelectedReport(report);
    setPreviewOpen(true);
    setPreviewLoading(true);
    setPreviewError("");
    try {
      const data = await fetchReportContent(report.filename);
      if (generation !== epoch.current || request !== previewRequest.current) return;
      if (!data || (!data.data_url && !data.html_content))
        throw new Error("未找到报告内容，文件可能已被清理。");
      if (data.filename !== report.filename) throw new Error("返回的文件名不一致，请关闭后重试。");
      setSelectedReport({ ...report, ...data });
    } catch (reason) {
      if (generation === epoch.current && request === previewRequest.current)
        setPreviewError(
          reason instanceof Error ? reason.message : "报告暂时无法加载，请关闭后重试。",
        );
    } finally {
      if (generation === epoch.current && request === previewRequest.current)
        setPreviewLoading(false);
    }
  };

  const closePreview = () => {
    previewRequest.current++;
    setPreviewOpen(false);
    setSelectedReport(null);
    setPreviewLoading(false);
    setPreviewError("");
  };

  const downloadReport = async (report: ReportItem) => {
    if (downloads.current.has(report.filename)) return;
    const generation = epoch.current;
    downloads.current.add(report.filename);
    setDownloadingFiles(new Set(downloads.current));
    setDownloadFailure(null);
    let blobUrl: string | null = null;
    try {
      const data =
        report.html_content || report.data_url ? report : await fetchReportContent(report.filename);
      if (generation !== epoch.current) return;
      if (!data || (!data.data_url && !data.html_content))
        throw new Error("未找到报告内容，文件可能已被清理。");
      if (data.filename !== report.filename) throw new Error("返回的文件名不一致，请刷新后重试。");
      const isHtml = Boolean(report.is_html || /\.html?$/i.test(report.filename));
      let href = data.data_url;
      if (isHtml && data.html_content) {
        blobUrl = URL.createObjectURL(
          new Blob([data.html_content], { type: "text/html;charset=utf-8" }),
        );
        href = blobUrl;
      }
      if (!href) throw new Error("没有可下载的文件内容。");
      const link = document.createElement("a");
      link.href = href;
      link.download = report.filename;
      document.body.appendChild(link);
      try {
        link.click();
      } finally {
        link.remove();
      }
      toast.success(`已开始下载 ${report.filename}`);
    } catch (reason) {
      if (generation === epoch.current)
        setDownloadFailure({
          filename: report.filename,
          message:
            reason instanceof Error
              ? `下载 ${report.filename} 失败：${reason.message}`
              : "下载失败，请重试。",
        });
    } finally {
      if (blobUrl) {
        // 留出浏览器接收下载的时间，再释放临时地址；卸载时也统一清理。
        const url = blobUrl;
        blobUrls.current.set(
          url,
          window.setTimeout(() => {
            URL.revokeObjectURL(url);
            blobUrls.current.delete(url);
          }, 1000),
        );
      }
      if (generation === epoch.current) {
        downloads.current.delete(report.filename);
        setDownloadingFiles(new Set(downloads.current));
      }
    }
  };

  return {
    previewOpen,
    previewLoading,
    previewError:
      previewError ||
      (downloadFailure?.filename === selectedReport?.filename ? downloadFailure?.message : "") ||
      "",
    selectedReport,
    openPreview,
    closePreview,
    downloadingFiles,
    downloadError: downloadFailure?.message ?? "",
    downloadReport,
  };
}
