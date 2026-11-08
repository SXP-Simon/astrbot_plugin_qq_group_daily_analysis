import { IconArrowDown, IconArrowUp, IconArrowsSort, IconEye } from "@tabler/icons-react";
import type { TraceRecord } from "../../entities/trace/model/types";
import type { TraceSortField, TraceSortOrder } from "../../entities/trace/model/traceQuery";
import { StatusTag } from "../../shared/ui/StatusTag";
import { TriggerTypeTag } from "../../shared/ui/TriggerTypeTag";
import { Button } from "../../shared/ui/button";
import { Pagination } from "../../shared/ui/pagination";
import { formatDuration, formatTokens, formatTimestamp } from "../../shared/lib/formatters";

interface TraceTableProps {
  traces: TraceRecord[];
  total: number;
  loading: boolean;
  page: number;
  pageSize: number;
  sortField: TraceSortField;
  sortOrder: TraceSortOrder;
  onViewTrace: (traceId: string) => void;
  onPageChange: (page: number, pageSize: number) => void;
  onSortChange: (field: TraceSortField) => void;
}

const sortedColumns: { label: string; field: TraceSortField }[] = [
  { label: "耗时", field: "duration_ms" },
  { label: "模型消耗", field: "total_tokens" },
  { label: "消息留存率", field: "compression_ratio" },
  { label: "开始时间", field: "started_at" },
];

export function TraceTable({
  traces,
  total,
  loading,
  page,
  pageSize,
  sortField,
  sortOrder,
  onViewTrace,
  onPageChange,
  onSortChange,
}: TraceTableProps) {
  return (
    <div aria-busy={loading}>
      {loading && (
        <p role="status" className="text-sm text-muted-foreground">
          正在更新分析记录…
        </p>
      )}
      <div
        className="overflow-x-auto rounded-xl border border-solid border-border bg-card focus-visible:outline-2 focus-visible:outline-ring"
        role="region"
        aria-label="分析记录列表"
        tabIndex={0}
      >
        <table className="ui-data-table w-full min-w-[1080px] border-collapse text-left text-sm">
          <caption className="sr-only">
            分析记录，可按耗时、模型消耗、消息留存率或开始时间排序
          </caption>
          <thead className="bg-muted text-muted-foreground">
            <tr>
              {["群聊 / 平台", "任务编号", "触发方式", "状态"].map((title) => (
                <th key={title} scope="col" className="px-4 py-3 font-medium">
                  {title}
                </th>
              ))}
              {sortedColumns.map(({ label, field }) => {
                const Icon =
                  sortField === field
                    ? sortOrder === "desc"
                      ? IconArrowDown
                      : IconArrowUp
                    : IconArrowsSort;
                return (
                  <th
                    scope="col"
                    key={field}
                    aria-sort={
                      sortField === field
                        ? sortOrder === "desc"
                          ? "descending"
                          : "ascending"
                        : "none"
                    }
                    className="px-2 py-2 font-medium"
                  >
                    <Button
                      variant="ghost"
                      size="sm"
                      className={sortField === field ? "bg-primary-soft text-primary-ink" : ""}
                      aria-label={`按${label}排序`}
                      onClick={() => onSortChange(field)}
                    >
                      {label}
                      <Icon aria-hidden="true" />
                    </Button>
                  </th>
                );
              })}
              <th scope="col" className="sticky right-0 bg-secondary px-4 py-3 font-medium">
                操作
              </th>
            </tr>
          </thead>
          <tbody>
            {traces.map((trace) => {
              const hasWarning =
                Boolean(trace.extra?.has_warnings) ||
                trace.spans?.some(
                  (span) =>
                    span.status === "warning" ||
                    span.payload?.success === false ||
                    Boolean(span.payload?.warning) ||
                    (Array.isArray(span.payload?.subtask_errors) &&
                      span.payload.subtask_errors.length > 0),
                );
              const status =
                ["succeeded", "completed"].includes(trace.status) && hasWarning
                  ? "warning"
                  : trace.status;
              const fallback =
                trace.extra?.fallback_to_fresh_run === true ||
                trace.extra?.resumed_from === "fresh_run_fallback";
              const ratio = trace.compression_ratio;
              const retention =
                typeof ratio === "number" && Number.isFinite(ratio) && ratio >= 0
                  ? `${Math.round(ratio * 100)}%`
                  : "未记录";
              return (
                <tr key={trace.trace_id} className="border-0 border-t border-solid border-border">
                  <td className="max-w-60 px-4 py-4">
                    <div className="break-words font-medium">{trace.group_name || "未知群"}</div>
                    <div className="mt-1 break-all font-mono text-xs text-muted-foreground">
                      {trace.platform && !["auto", "default"].includes(trace.platform)
                        ? `${trace.platform} · `
                        : ""}
                      {trace.group_id}
                    </div>
                  </td>
                  <td className="max-w-52 px-4 py-4">
                    <Button
                      variant="link"
                      size="sm"
                      className="h-auto whitespace-normal break-all p-0 text-left font-mono text-xs text-secondary-ink"
                      onClick={() => onViewTrace(trace.trace_id)}
                    >
                      {trace.trace_id}
                    </Button>
                  </td>
                  <td className="whitespace-nowrap px-4 py-4">
                    <TriggerTypeTag triggerType={trace.trigger_type} />
                    {fallback && (
                      <details className="mt-1 text-xs text-muted-foreground">
                        <summary className="cursor-pointer">已重新全量分析</summary>
                        未找到历史快照，本次重新拉取消息进行分析。
                      </details>
                    )}
                  </td>
                  <td className="px-4 py-4">
                    <StatusTag status={status} />
                  </td>
                  <td className="px-4 py-4 font-mono text-xs">
                    {typeof trace.duration_ms === "number" &&
                    Number.isFinite(trace.duration_ms) &&
                    trace.duration_ms >= 0
                      ? trace.duration_ms === 0
                        ? "0ms"
                        : formatDuration(trace.duration_ms)
                      : "未记录"}
                  </td>
                  <td className="px-4 py-4 font-mono text-xs">
                    {formatTokens(trace.total_tokens ?? undefined)}
                  </td>
                  <td className="px-4 py-4 font-mono text-xs">
                    <div>{retention}</div>
                    <div className="mt-1 whitespace-nowrap text-muted-foreground">
                      有效 {trace.cleaned_message_count ?? "未记录"} / 拉取{" "}
                      {trace.raw_message_count ?? "未记录"}
                    </div>
                  </td>
                  <td className="whitespace-nowrap px-4 py-4 font-mono text-xs">
                    {formatTimestamp(trace.started_at)}
                  </td>
                  <td className="sticky right-0 bg-card px-3 py-4">
                    <Button variant="tonal" size="sm" onClick={() => onViewTrace(trace.trace_id)}>
                      <IconEye aria-hidden="true" />
                      详情
                    </Button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {!loading && traces.length === 0 && (
          <p className="py-12 text-center text-muted-foreground">暂无符合条件的分析记录</p>
        )}
      </div>
      <Pagination
        page={page}
        pageSize={pageSize}
        total={total}
        loading={loading}
        onChange={onPageChange}
      />
    </div>
  );
}
