import type { TraceSpan } from "./types";

/** 已保存耗时优先；只有仍在运行且开始时间有效的阶段才显示实时经过时间。 */
export function getSpanTiming(
  span: Pick<TraceSpan, "duration_ms" | "started_at" | "status">,
  taskStatus?: string,
  now = Date.now(),
): { durationMs: number | null; live: boolean } {
  if (
    typeof span.duration_ms === "number" &&
    Number.isFinite(span.duration_ms) &&
    span.duration_ms >= 0
  )
    return { durationMs: span.duration_ms, live: false };
  const started = span.started_at * 1000;
  if (
    span.status === "running" &&
    taskStatus === "running" &&
    Number.isFinite(started) &&
    started > 0 &&
    started <= now
  )
    return { durationMs: now - started, live: true };
  return { durationMs: null, live: false };
}

/** 比例用于比较耗时，不表示完成进度；保留超过分母的真实比例，便于检查异常记录。 */
export function getDurationRatio(
  durationMs: number | null,
  denominatorMs?: number | null,
): number | null {
  if (
    durationMs === null ||
    !Number.isFinite(durationMs) ||
    durationMs < 0 ||
    denominatorMs == null ||
    !Number.isFinite(denominatorMs) ||
    denominatorMs <= 0
  )
    return null;
  return (durationMs / denominatorMs) * 100;
}
