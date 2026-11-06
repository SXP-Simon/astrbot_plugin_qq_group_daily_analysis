import { useState } from "react";
import { IconCopy } from "@tabler/icons-react";
import type { TraceRecord } from "../../../entities/trace/model/types";
import {
  formatDuration,
  formatTokens,
  formatTimestamp,
  formatPercent,
  formatTriggerType,
} from "../../../shared/lib/formatters";
import { copyToClipboard } from "../../../shared/lib/clipboard";
import { Button } from "../../../shared/ui/button";
import { TraceReportFiles } from "./TraceReportFiles";

interface TraceSummaryCardProps {
  trace: TraceRecord;
  downloading?: boolean;
  onPreviewFile: (filename: string, isHtml: boolean) => void;
  onDownloadFile: (filename: string, isHtml: boolean) => void;
}

export function TraceSummaryCard({
  trace,
  downloading,
  onPreviewFile,
  onDownloadFile,
}: TraceSummaryCardProps) {
  const [copied, setCopied] = useState<{ id: string; message: string } | null>(null);
  const fallback = Boolean(
    trace.extra?.fallback_to_fresh_run || trace.extra?.resumed_from === "fresh_run_fallback",
  );
  const rawFiles: unknown[] =
    trace.report_files ??
    (Array.isArray(trace.extra?.report_files) ? trace.extra.report_files : []);
  const names = new Set<string>();
  const files = rawFiles.flatMap((file) => {
    if (
      !file ||
      typeof file !== "object" ||
      !("filename" in file) ||
      typeof file.filename !== "string" ||
      !file.filename ||
      names.has(file.filename)
    )
      return [];
    names.add(file.filename);
    return [
      {
        filename: file.filename,
        isHtml: ("format" in file && file.format === "html") || /\.html?$/i.test(file.filename),
        isComic:
          ("report_type" in file && file.report_type === "comic") ||
          /^(comic_|漫画_)/i.test(file.filename),
        size:
          "size_bytes" in file && typeof file.size_bytes === "number" ? file.size_bytes : undefined,
      },
    ];
  });
  const raw = trace.context_metrics?.raw_message_count ?? trace.raw_message_count;
  const cleaned = trace.context_metrics?.cleaned_message_count ?? trace.cleaned_message_count;
  const duration = trace.duration_ms;
  return (
    <section aria-label="任务摘要" className="grid gap-4">
      {fallback && (
        <p role="status" className="m-0 rounded-xl bg-muted px-4 py-3 text-sm">
          历史快照缺失，本次续跑已改为重新拉取消息并分析。
        </p>
      )}
      <dl className="m-0 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div>
          <dt className="text-sm text-muted-foreground">已记录耗时</dt>
          <dd className="m-0 text-xl">
            {duration != null && Number.isFinite(duration) && duration >= 0
              ? duration === 0
                ? "0ms"
                : formatDuration(duration)
              : "未记录"}
          </dd>
        </div>
        <div>
          <dt className="text-sm text-muted-foreground">有效 / 拉取消息</dt>
          <dd className="m-0 text-xl">
            {cleaned?.toLocaleString() ?? "—"}
            <span className="text-sm text-muted-foreground"> / {raw?.toLocaleString() ?? "—"}</span>
          </dd>
        </div>
        <div>
          <dt className="text-sm text-muted-foreground">消耗 Tokens</dt>
          <dd className="m-0 text-xl">
            {formatTokens(trace.token_usage?.total_tokens ?? trace.total_tokens ?? undefined)}
          </dd>
        </div>
        <div>
          <dt className="text-sm text-muted-foreground">报告文件</dt>
          <dd className="m-0 text-xl">
            {files.length} <span className="text-sm">份</span>
          </dd>
        </div>
      </dl>
      <details className="text-sm">
        <summary className="cursor-pointer text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring">
          任务与消耗明细
        </summary>
        <dl className="my-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 [&_dt]:text-muted-foreground [&_dd]:m-0 [&_dd]:break-words">
          <div>
            <dt>任务编号</dt>
            <dd className="font-mono text-xs">
              {trace.trace_id}
              <Button
                size="sm"
                variant="ghost"
                aria-label="复制任务编号"
                onClick={async () =>
                  setCopied({
                    id: trace.trace_id,
                    message: (await copyToClipboard(trace.trace_id))
                      ? "已复制"
                      : "无法复制，请手动选择。",
                  })
                }
              >
                <IconCopy aria-hidden="true" />
              </Button>
              {copied?.id === trace.trace_id && <span role="status">{copied.message}</span>}
            </dd>
          </div>
          <div>
            <dt>群聊</dt>
            <dd>
              {trace.group_name || "未记录名称"} ·{" "}
              <span className="font-mono">{trace.group_id}</span>
            </dd>
          </div>
          <div>
            <dt>平台</dt>
            <dd>{trace.platform || "未记录"}</dd>
          </div>
          <div>
            <dt>触发方式</dt>
            <dd>{formatTriggerType(trace.trigger_type).text}</dd>
          </div>
          <div>
            <dt>开始时间</dt>
            <dd>{formatTimestamp(trace.started_at)}</dd>
          </div>
          <div>
            <dt>结束时间</dt>
            <dd>{trace.completed_at ? formatTimestamp(trace.completed_at) : "未记录"}</dd>
          </div>
          <div>
            <dt>消息保留比例</dt>
            <dd>
              {formatPercent(
                trace.context_metrics?.compression_ratio ?? trace.compression_ratio ?? undefined,
              )}
            </dd>
          </div>
          <div>
            <dt>输入 / 输出 Tokens</dt>
            <dd>
              {formatTokens(trace.token_usage?.prompt_tokens)} /{" "}
              {formatTokens(trace.token_usage?.completion_tokens)}
            </dd>
          </div>
          {trace.estimated_cost != null && (
            <div>
              <dt>预估费用（美元）</dt>
              <dd>{trace.estimated_cost}</dd>
            </div>
          )}
        </dl>
      </details>
      <TraceReportFiles
        files={files}
        downloading={downloading}
        onPreviewFile={onPreviewFile}
        onDownloadFile={onDownloadFile}
      />
    </section>
  );
}
