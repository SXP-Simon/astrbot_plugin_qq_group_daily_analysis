import { IconChevronDown, IconChevronRight, IconLoader2 } from "@tabler/icons-react";
import { resolveSpanOutcome } from "../model/spanOutcome";
import { getSpanTiming, getDurationRatio } from "../model/spanTiming";
import { getStageSlaThreshold } from "../model/sla";
import { formatDuration, formatStageName } from "../../../shared/lib/formatters";

interface SpanHeaderProps {
  stageName: string;
  durationMs?: number | null;
  startedAt: number;
  totalDurationMs?: number | null;
  status: string;
  taskStatus?: string;
  isExpanded: boolean;
  isSelected?: boolean;
  onToggleExpand: () => void;
  payload?: Record<string, unknown>;
  parentStageName?: string;
  hasChildren?: boolean;
  now?: number;
}

export function SpanHeader({
  stageName,
  durationMs,
  startedAt,
  totalDurationMs,
  status,
  taskStatus,
  isExpanded,
  isSelected,
  onToggleExpand,
  payload,
  parentStageName,
  hasChildren = false,
  now,
}: SpanHeaderProps) {
  const outcome = resolveSpanOutcome(status, payload);
  const timing = getSpanTiming(
    { duration_ms: durationMs, started_at: startedAt, status },
    taskStatus,
    now,
  );
  const ratio = getDurationRatio(timing.durationMs, totalDurationMs);
  const ratioLabel =
    ratio !== null && ratio > 0 && ratio < 0.1 ? "<0.1" : ratio?.toFixed(1).replace(/\.0$/, "");
  const duration = timing.durationMs === null ? "耗时未记录" : formatDuration(timing.durationMs);
  const labels = {
    cancelled: "已取消",
    failed: "失败",
    warning: "警告",
    success: "完成",
    skipped: "已跳过",
    unknown: "状态未记录",
    running: taskStatus === "running" ? "执行中" : "状态未更新",
  };
  const { thresholdMs, description } = getStageSlaThreshold(stageName);
  const slow =
    !timing.live &&
    timing.durationMs !== null &&
    timing.durationMs > thresholdMs &&
    outcome !== "cancelled";

  return (
    <button
      type="button"
      className="stage-row"
      data-selected={isSelected || undefined}
      data-outcome={outcome}
      aria-current={isSelected ? "true" : undefined}
      aria-expanded={hasChildren ? isExpanded : undefined}
      onClick={onToggleExpand}
    >
      <span className="stage-row-heading">
        {hasChildren ? (
          isExpanded ? (
            <IconChevronDown size={16} aria-hidden="true" />
          ) : (
            <IconChevronRight size={16} aria-hidden="true" />
          )
        ) : (
          <IconChevronRight size={16} aria-hidden="true" />
        )}
        <span className="stage-name">
          {formatStageName(stageName)}
          {stageName === "IMAGE_RENDER_ATTEMPT" &&
            typeof payload?.strategy_name === "string" &&
            ` · ${payload.strategy_name}`}
        </span>
        {hasChildren && <small>含子阶段</small>}
      </span>
      <span className="stage-row-meta">
        {outcome === "running" && taskStatus === "running" && (
          <IconLoader2 size={14} className="animate-spin" aria-hidden="true" />
        )}
        <span>
          {labels[outcome]} ({timing.live ? "已运行 " : ""}
          {duration})
        </span>
        {ratio !== null && (
          <span
            title={
              parentStageName
                ? `相对于「${formatStageName(parentStageName)}」耗时；父子不能重复累加，并行阶段不累计为任务耗时。`
                : "相对于本次任务总耗时，不表示完成进度。"
            }
          >
            {parentStageName ? "占父阶段" : "占总耗时"} {ratioLabel}%
          </span>
        )}
      </span>
      {ratio !== null && (
        <span className="stage-duration-track" aria-hidden="true">
          <span style={{ width: `${Math.min(100, ratio)}%` }} />
        </span>
      )}
      {slow && (
        <small className="stage-slow" title={description}>
          耗时超出参考值
        </small>
      )}
    </button>
  );
}
