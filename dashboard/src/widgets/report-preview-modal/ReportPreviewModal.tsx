import { HtmlPreview } from "../../shared/ui/html-preview";
import { ImageViewer } from "../../shared/ui/image-preview";
import { LoadingState } from "../../shared/ui/loading-state";
import { useState } from "react";
import { IconDownload, IconCopy } from "@tabler/icons-react";
import type { ReportItem } from "../../entities/report/model/types";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "../../shared/ui/dialog";
import { Button } from "../../shared/ui/button";
import { copyToClipboard } from "../../shared/lib/clipboard";

interface ReportPreviewModalProps {
  open: boolean;
  loading: boolean;
  report: ReportItem | null;
  error?: string | null;
  downloading?: boolean;
  onClose: () => void;
  onDownload: (report: ReportItem) => void;
  onRetry?: () => void;
}

export function ReportPreviewModal({
  open,
  loading,
  report,
  error,
  downloading,
  onClose,
  onDownload,
  onRetry,
}: ReportPreviewModalProps) {
  const [copyResult, setCopyResult] = useState<{ path: string; message: string } | null>(null);
  const isHtml = Boolean(report?.is_html || /\.html?$/i.test(report?.filename || ""));
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) onClose();
      }}
    >
      <DialogContent className="max-w-6xl">
        <DialogTitle>报告预览</DialogTitle>
        <DialogDescription className="break-all font-mono text-xs">
          {report?.filename || "正在读取报告"}
        </DialogDescription>
        {error && (
          <p role="alert" className="m-0 text-sm text-destructive">
            {error}
            {onRetry && (
              <Button className="ml-2" variant="outline" onClick={onRetry}>
                重新加载
              </Button>
            )}
          </p>
        )}
        {loading ? (
          <LoadingState skeleton className="py-12 text-center text-muted-foreground">
            正在加载报告…
          </LoadingState>
        ) : (
          <>
            {report?.absolute_path && (
              <details className="text-sm">
                <summary className="cursor-pointer text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring">
                  服务器文件位置
                </summary>
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <code className="min-w-0 break-all text-xs">{report.absolute_path}</code>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={async () => {
                      const path = report.absolute_path;
                      if (!path) return;
                      setCopyResult({
                        path,
                        message: (await copyToClipboard(path))
                          ? "已复制路径"
                          : "无法复制，请手动选择路径。",
                      });
                    }}
                  >
                    <IconCopy aria-hidden="true" />
                    复制路径
                  </Button>
                  {copyResult?.path === report.absolute_path && (
                    <span role="status">{copyResult.message}</span>
                  )}
                </div>
              </details>
            )}
            {isHtml && (report?.html_content || report?.data_url) ? (
              <HtmlPreview
                title={report.filename}
                html={report.html_content || undefined}
                src={report.data_url || undefined}
                sandbox="allow-scripts allow-same-origin"
                className="block h-[65dvh] w-full rounded-xl border border-solid border-border bg-white"
              />
            ) : report?.data_url ? (
              <ImageViewer src={report.data_url} title={report.filename} fitMode="width" />
            ) : (
              !error && <p className="py-12 text-center text-muted-foreground">未找到报告内容</p>
            )}
          </>
        )}
        <div className="flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            关闭预览
          </Button>
          {report && (
            <Button onClick={() => onDownload(report)} disabled={loading || downloading}>
              <IconDownload aria-hidden="true" />
              {downloading ? "正在下载…" : isHtml ? "下载 HTML" : "下载图片"}
            </Button>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
