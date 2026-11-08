import type { TraceRecord, TraceSpan } from "./types";
import { buildSpanTree, spanGroupKey, type SpanTreeNode } from "./spanTree";
import { getDurationRatio } from "./spanTiming";
import { formatStageName } from "../../../shared/lib/formatters";

export type MetricsViewMode = "duration" | "memory" | "dataflow";
export type PipelineMode = "effective" | "all";

export interface MetricStage {
  span: TraceSpan;
  label: string;
  depth: number;
  durationMs: number | null;
  ratio: number | null;
  denominator: "父阶段" | "任务总耗时";
  attempt: number;
  attempts: number;
}

/** 缺失或无效采样保留为空，不能补成零。 */
function recordedNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;
}

export function getTraceMetrics(trace: TraceRecord, mode: PipelineMode) {
  const spans = trace.spans || [];
  const groups = new Map<string, TraceSpan[]>();
  for (const span of spans) {
    const key = spanGroupKey(span);
    const attempts = groups.get(key) || [];
    attempts.push(span);
    groups.set(key, attempts);
  }
  const stages: MetricStage[] = [];
  const labels = new Map<string, number>();
  const visit = (nodes: SpanTreeNode[], depth: number, parent?: TraceSpan) => {
    for (const node of nodes) {
      const span = node.span;
      const attempts = groups.get(spanGroupKey(span)) || [span];
      // 精简视图隐藏前序尝试的整棵子树，保留不同渲染方案各自的子阶段。
      if (mode === "effective" && attempts[attempts.length - 1] !== span) continue;
      const durationMs = recordedNumber(span.duration_ms);
      const attempt = attempts.indexOf(span) + 1;
      const strategy =
        typeof span.payload.strategy_name === "string" ? ` · ${span.payload.strategy_name}` : "";
      const ordinal = (labels.get(span.stage_name) || 0) + 1;
      labels.set(span.stage_name, ordinal);
      const label = `${formatStageName(span.stage_name)}${strategy}${attempts.length > 1 ? ` · 第 ${attempt}/${attempts.length} 次` : ordinal > 1 ? ` #${ordinal}` : ""}`;
      stages.push({
        span,
        label,
        depth,
        durationMs,
        attempt,
        attempts: attempts.length,
        ratio: getDurationRatio(
          durationMs,
          parent ? recordedNumber(parent.duration_ms) : recordedNumber(trace.duration_ms),
        ),
        denominator: parent ? "父阶段" : "任务总耗时",
      });
      visit(node.children, depth + 1, span);
    }
  };
  visit(buildSpanTree(spans), 0);

  const perf = trace.performance_metrics;
  const memory = [{ label: "开始", rss: recordedNumber(perf?.init_memory_mb) }];
  const ordered = [...stages].sort((a, b) => {
    const endA =
      a.durationMs !== null ? a.span.started_at * 1000 + a.durationMs : Number.POSITIVE_INFINITY;
    const endB =
      b.durationMs !== null ? b.span.started_at * 1000 + b.durationMs : Number.POSITIVE_INFINITY;
    return endA - endB;
  });
  for (const item of ordered)
    memory.push({
      label: item.label,
      rss:
        recordedNumber(item.span.end_memory_mb) ?? recordedNumber(item.span.payload.end_memory_mb),
    });
  memory.push({ label: "结束", rss: recordedNumber(perf?.final_memory_mb) });
  const memorySamples = memory.map((point, index) => {
    const previous = index > 0 ? memory[index - 1].rss : null;
    return {
      ...point,
      delta: point.rss !== null && previous !== null ? point.rss - previous : null,
    };
  });

  const render = [...spans]
    .reverse()
    .find((span) => ["RENDER_REPORT", "REPORT_RENDERING"].includes(span.stage_name));
  const dispatch = [...spans]
    .reverse()
    .find((span) => ["DISPATCH_REPORT", "MESSAGE_DISPATCH"].includes(span.stage_name));
  const bytes = recordedNumber(render?.payload.image_bytes);
  const imageKb = bytes !== null ? bytes / 1024 : recordedNumber(dispatch?.payload.raw_image_kb);
  const base64Kb = recordedNumber(dispatch?.payload.base64_payload_kb);
  const base64 =
    dispatch?.payload.transmission_mode === "base64" || (base64Kb !== null && base64Kb > 0);
  const dataflow = [
    { label: "HTML 源码", sizeKb: recordedNumber(render?.payload.html_size_kb) },
    { label: "原始图片", sizeKb: imageKb },
    {
      label: base64 ? "Base64 传输载荷" : "网络传输载荷",
      sizeKb: base64 ? base64Kb : recordedNumber(dispatch?.payload.raw_image_kb),
    },
  ];

  return {
    stages,
    memory: memorySamples,
    dataflow,
    totalDurationMs: recordedNumber(trace.duration_ms),
    peakMemoryMb: recordedNumber(perf?.peak_memory_mb),
    deltaMemoryMb:
      typeof perf?.delta_memory_mb === "number" && Number.isFinite(perf.delta_memory_mb)
        ? perf.delta_memory_mb
        : null,
    retryGroups: [...groups.values()]
      .filter((attempts) => attempts.length > 1)
      .map((attempts) => ({
        label: formatStageName(attempts[0].stage_name),
        attempts: attempts.length,
      })),
  };
}

export type TraceMetrics = ReturnType<typeof getTraceMetrics>;
