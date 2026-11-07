import {
  IconFileText,
  IconPhoto,
  IconDownload,
  IconEye,
  IconPalette,
  IconArrowUpRight,
} from "@tabler/icons-react";
import type { ReportItem } from "../../entities/report/model/types";
import { Button } from "../../shared/ui/button";
import { formatTimestamp } from "../../shared/lib/formatters";

interface ReportListProps {
  reports: ReportItem[];
  downloadingFiles: ReadonlySet<string>;
  onPreview: (report: ReportItem) => void;
  onDownload: (report: ReportItem) => void;
  onRerender: (report: ReportItem) => void;
  onViewTrace?: (id: string) => void;
}

export function ReportList({
  reports,
  downloadingFiles,
  onPreview,
  onDownload,
  onRerender,
  onViewTrace,
}: ReportListProps) {
  return (
    <ul aria-label="报告文件" className="m-0 list-none divide-y divide-border p-0">
      {reports.map((report) => {
        const isHtml = Boolean(report.is_html || /\.html?$/i.test(report.filename));
        const isComic = Boolean(report.is_comic || /^(comic_|漫画_)/i.test(report.filename));
        const fileTone = isComic
          ? "bg-creative/10 text-creative"
          : isHtml
            ? "bg-warning/10 text-warning"
            : "bg-info/10 text-info";
        const Icon = isHtml ? IconFileText : IconPhoto;
        const time = report.modified_at ?? report.created_at;
        const busy = downloadingFiles.has(report.filename);
        return (
          <li
            key={report.filename}
            className="grid min-w-0 gap-3 py-5 lg:grid-cols-[minmax(0,2fr)_minmax(0,1fr)_auto] lg:items-center"
          >
            <div className="min-w-0 space-y-2">
              <div className="flex items-start gap-2">
                <span
                  className={`inline-flex size-8 shrink-0 items-center justify-center rounded-lg ${fileTone}`}
                >
                  <Icon aria-hidden="true" className="size-4" />
                </span>
                <span className="break-all font-mono text-sm">{report.filename}</span>
              </div>
              <p className="m-0 flex flex-wrap gap-x-3 gap-y-1 text-xs text-muted-foreground">
                <span className={isComic ? "text-creative" : isHtml ? "text-warning" : "text-info"}>
                  {isComic ? "群漫画" : isHtml ? "交互式 HTML" : "图片报告"}
                </span>
                <span>
                  {Number.isFinite(report.size_bytes) && report.size_bytes >= 0
                    ? `${(report.size_bytes / 1024).toFixed(1)} KB`
                    : "大小未记录"}
                </span>
                <span>
                  {typeof time === "number" && Number.isFinite(time)
                    ? formatTimestamp(time)
                    : "时间未记录"}
                </span>
              </p>
            </div>
            <div className="min-w-0 space-y-1">
              <p className="m-0 break-words text-sm">
                {report.group_name || report.group_id || "群聊未记录"}
              </p>
              <p className="m-0 break-all font-mono text-xs text-muted-foreground">
                {report.platform && !["auto", "default"].includes(report.platform)
                  ? report.platform
                  : "平台未记录"}
                {report.group_id && ` · ${report.group_id}`}
              </p>
              {report.trace_id ? (
                onViewTrace ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-auto max-w-full gap-1 px-0 py-1 text-xs text-info hover:bg-info/10"
                    onClick={() => report.trace_id && onViewTrace(report.trace_id)}
                  >
                    查看任务
                    <IconArrowUpRight aria-hidden="true" />
                    <span className="truncate font-mono">{report.trace_id}</span>
                  </Button>
                ) : (
                  <p className="m-0 break-all font-mono text-xs text-muted-foreground">
                    {report.trace_id}
                  </p>
                )
              ) : (
                <span className="text-xs text-muted-foreground">未关联分析任务</span>
              )}
            </div>
            <div className="flex flex-wrap gap-2">
              <Button
                variant="ghost"
                className="bg-info/10 text-info hover:bg-info/15"
                size="sm"
                onClick={() => onPreview(report)}
              >
                <IconEye aria-hidden="true" />
                预览
              </Button>
              {!isComic && (
                <Button
                  variant="outline"
                  className="border-creative/20 bg-creative/5 text-creative hover:bg-creative/10"
                  size="sm"
                  onClick={() => onRerender(report)}
                >
                  <IconPalette aria-hidden="true" />
                  换模板
                </Button>
              )}
              <Button variant="ghost" size="sm" disabled={busy} onClick={() => onDownload(report)}>
                <IconDownload aria-hidden="true" />
                {busy ? "下载中…" : "下载"}
              </Button>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
