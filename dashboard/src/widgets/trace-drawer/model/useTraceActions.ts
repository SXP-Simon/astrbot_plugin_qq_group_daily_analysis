import { useEffect, useRef, useState } from "react";
import { resumeTraceTask } from "../../../entities/trace/api/traceApi";
import { fetchReportContent } from "../../../entities/report/api/reportApi";
import type { TraceRecord } from "../../../entities/trace/model/types";
import type { ReportItem } from "../../../entities/report/model/types";

export function useTraceActions(
  sourceId: string | null,
  open: boolean,
  trace: TraceRecord | null,
  onResumed: (traceId: string) => void,
) {
  const generation = useRef(0);
  const previewSequence = useRef(0);
  const resumePending = useRef(false);
  const downloadPending = useRef(false);
  const [resumeModalOpen, setResumeModalOpen] = useState(false);
  const [resuming, setResuming] = useState(false);
  const [previewReport, setPreviewReport] = useState<ReportItem | null>(null);
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    const pending = generation;
    generation.current++;
    previewSequence.current++;
    resumePending.current = false;
    downloadPending.current = false;
    setResumeModalOpen(false);
    setResuming(false);
    setPreviewOpen(false);
    setPreviewReport(null);
    setPreviewLoading(false);
    setPreviewError(null);
    setDownloading(false);
    setActionError(null);
    setNotice(null);
    return () => {
      pending.current++;
    };
  }, [sourceId, open]);

  const closePreview = () => {
    previewSequence.current++;
    setPreviewOpen(false);
    setPreviewReport(null);
    setPreviewLoading(false);
    setPreviewError(null);
  };

  const previewFile = async (filename: string, isHtml: boolean) => {
    if (!open || !trace) return;
    const epoch = generation.current;
    const request = ++previewSequence.current;
    const base: ReportItem = {
      filename,
      size_bytes: 0,
      modified_at: Date.now() / 1000,
      is_html: isHtml,
      group_id: trace.group_id,
      group_name: trace.group_name,
      platform: trace.platform,
      trace_id: trace.trace_id,
    };
    setPreviewReport(base);
    setPreviewOpen(true);
    setPreviewLoading(true);
    setPreviewError(null);
    setActionError(null);
    try {
      const report = await fetchReportContent(filename);
      if (epoch !== generation.current || request !== previewSequence.current) return;
      if (report) setPreviewReport({ ...base, ...report });
      else setPreviewError("没有找到报告内容，文件可能已被清理。");
    } catch {
      if (epoch === generation.current && request === previewSequence.current)
        setPreviewError("报告暂时无法加载，请关闭后重试。");
    } finally {
      if (epoch === generation.current && request === previewSequence.current)
        setPreviewLoading(false);
    }
  };

  const downloadFile = async (filename: string, isHtml: boolean) => {
    if (!open || downloadPending.current) return;
    const epoch = generation.current;
    downloadPending.current = true;
    setDownloading(true);
    setActionError(null);
    let blobUrl: string | undefined;
    try {
      const report = await fetchReportContent(filename);
      if (epoch !== generation.current) return;
      if (!report) throw new Error("没有找到报告文件。");
      let href = report.data_url;
      if (isHtml && report.html_content) {
        blobUrl = URL.createObjectURL(
          new Blob([report.html_content], { type: "text/html;charset=utf-8" }),
        );
        href = blobUrl;
      }
      if (!href) throw new Error("报告没有可下载的内容。");
      const link = document.createElement("a");
      link.href = href;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
    } catch (error) {
      if (epoch === generation.current)
        setActionError(
          error instanceof Error ? `下载失败：${error.message}` : "下载失败，请稍后重试。",
        );
    } finally {
      if (blobUrl) URL.revokeObjectURL(blobUrl);
      if (epoch === generation.current) {
        downloadPending.current = false;
        setDownloading(false);
      }
    }
  };

  const confirmResume = async (provider?: string, template?: string) => {
    const traceId = trace?.trace_id || sourceId;
    if (!open || !traceId || resumePending.current) return;
    const epoch = generation.current;
    resumePending.current = true;
    setResuming(true);
    setActionError(null);
    try {
      const result = await resumeTraceTask(traceId, provider, template);
      if (epoch !== generation.current) return;
      closePreview();
      onResumed(result.trace_id);
      setResumeModalOpen(false);
      setNotice("续跑任务已提交，正在查看该任务的执行记录。");
    } catch (error) {
      if (epoch === generation.current)
        setActionError(
          error instanceof Error ? `续跑未成功：${error.message}` : "续跑未成功，请稍后重试。",
        );
    } finally {
      if (epoch === generation.current) {
        resumePending.current = false;
        setResuming(false);
      }
    }
  };

  return {
    resumeModalOpen: open && resumeModalOpen,
    setResumeModalOpen,
    resuming,
    confirmResume,
    previewReport,
    previewOpen: open && previewOpen,
    previewLoading,
    previewError,
    previewFile,
    closePreview,
    downloadFile,
    downloading,
    actionError,
    notice,
  };
}
