import { expect, it } from "vitest";
import { getTraceMetrics } from "@/entities/trace/model/traceMetrics";
import type { TraceRecord, TraceSpan } from "@/entities/trace/model/types";

const base: TraceRecord = {
  trace_id: "example",
  group_id: "example",
  group_name: "示例",
  platform: "telegram",
  trigger_type: "manual",
  status: "succeeded",
  started_at: 1,
};
function span(id: string, duration: number | null, parent?: string): TraceSpan {
  return {
    span_id: id,
    trace_id: "example",
    stage_name: id,
    status: "success",
    started_at: 1,
    duration_ms: duration,
    payload: parent ? { parent_span_id: parent } : {},
  };
}

it("任务耗时缺失时不累加父子或并行阶段，子阶段仍用真实父耗时", () => {
  const data = getTraceMetrics(
    { ...base, spans: [span("parent", 100), span("a", 80, "parent"), span("b", 80, "parent")] },
    "all",
  );
  expect(data.totalDurationMs).toBeNull();
  expect(data.stages.map((item) => item.ratio)).toEqual([null, 80, 80]);
  expect(data.stages.map((item) => item.denominator)).toEqual(["任务总耗时", "父阶段", "父阶段"]);
});

it("未知耗时保留空值，真实零耗时不丢失，运行中也不伪造图表采样", () => {
  const data = getTraceMetrics(
    {
      ...base,
      duration_ms: 100,
      status: "running",
      spans: [span("missing", null), span("zero", 0), { ...span("live", null), status: "running" }],
    },
    "all",
  );
  expect(data.stages.map((item) => item.durationMs)).toEqual([null, 0, null]);
  expect(data.stages.map((item) => item.ratio)).toEqual([null, 0, null]);
});

it("精简链路移除旧父阶段和子树，完整链路保留重试次序", () => {
  const old = { ...span("old", 100), stage_name: "RENDER_REPORT", status: "failed" };
  const next = { ...span("next", 50), stage_name: "RENDER_REPORT" };
  const trace = {
    ...base,
    spans: [old, span("old-child", 80, "old"), next, span("new-child", 40, "next")],
  };
  expect(getTraceMetrics(trace, "effective").stages.map((item) => item.span.span_id)).toEqual([
    "next",
    "new-child",
  ]);
  const all = getTraceMetrics(trace, "all");
  expect(all.stages.map((item) => item.span.span_id)).toEqual([
    "old",
    "old-child",
    "next",
    "new-child",
  ]);
  expect(all.stages[2].attempt).toBe(2);
  expect(all.retryGroups).toEqual([{ label: "报告长图渲染与生成", attempts: 2 }]);
});

it("不同父级下的渲染尝试保留为独立步骤，不合并为同名重试", () => {
  const trace = {
    ...base,
    spans: [
      span("render", 100),
      { ...span("a", 60, "render"), stage_name: "IMAGE_RENDER_ATTEMPT" },
      { ...span("b", 40, "render"), stage_name: "IMAGE_RENDER_ATTEMPT" },
    ],
  };
  const data = getTraceMetrics(trace, "effective");
  expect(data.stages).toHaveLength(3);
  expect(data.retryGroups).toHaveLength(0);
});

it("宿主内存缺测留空，不沿用上次读数，也不把子进程峰值混入宿主", () => {
  const trace: TraceRecord = {
    ...base,
    performance_metrics: {
      init_memory_mb: 50,
      final_memory_mb: 70,
      peak_memory_mb: 90,
      delta_memory_mb: 20,
    },
    spans: [
      { ...span("a", 10), end_memory_mb: 60 },
      { ...span("b", 20), payload: { worker_peak_rss_mb: 900 } },
      { ...span("c", 30), payload: { end_memory_mb: 65 } },
    ],
  };
  const data = getTraceMetrics(trace, "all");
  expect(data.memory.map((item) => item.rss)).toEqual([50, 60, null, 65, 70]);
  expect(data.memory.map((item) => item.delta)).toEqual([null, 10, null, null, 5]);
  expect(data.peakMemoryMb).toBe(90);
});

it("没有体积记录不推断为纯文本或未输出，Base64 保留真实大小", () => {
  expect(getTraceMetrics(base, "all").dataflow.map((item) => item.sizeKb)).toEqual([
    null,
    null,
    null,
  ]);
  const data = getTraceMetrics(
    {
      ...base,
      spans: [
        {
          ...span("render", 1),
          stage_name: "RENDER_REPORT",
          payload: { image_bytes: 2048, html_size_kb: 0 },
        },
        {
          ...span("send", 1),
          stage_name: "DISPATCH_REPORT",
          payload: { transmission_mode: "base64", base64_payload_kb: 2.7 },
        },
      ],
    },
    "all",
  );
  expect(data.dataflow.map((item) => item.sizeKb)).toEqual([0, 2, 2.7]);
});
