import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { SpanTimeline } from "../SpanTimeline";
import type { TraceSpan } from "../../model/types";
import { buildSpanTree } from "../../model/spanTree";

it("父阶段占任务总耗时，子阶段相对父阶段计算，短步骤不再抬高到2%", () => {
  const spans: TraceSpan[] = [
    { span_id: "render", trace_id: "test", stage_name: "RENDER_REPORT", status: "success", started_at: 1, duration_ms: 1000, payload: {} },
    { span_id: "validate", trace_id: "test", stage_name: "TYPST_VALIDATE", status: "success", started_at: 1, duration_ms: 3, payload: { parent_span_id: "render" } },
    { span_id: "compile", trace_id: "test", stage_name: "TYPST_COMPILE", status: "success", started_at: 1.003, duration_ms: 997, payload: { parent_span_id: "render" } },
    { span_id: "old", trace_id: "test", stage_name: "SAVE_SUMMARY", status: "success", started_at: 2, duration_ms: 0, payload: { parent_span_id: "missing" } },
  ];
  render(<SpanTimeline spans={spans} totalDurationMs={2000} taskStatus="succeeded" />);
  expect(screen.getByText("含子阶段")).toBeVisible();
  expect(screen.getByText("占总耗时 50%")).toBeVisible();
  expect(screen.queryByText("Typst 模板与字体检查")).not.toBeInTheDocument();
  fireEvent.click(screen.getByText("报告长图渲染与生成"));
  expect(screen.getByText("占父阶段 0.3%")).toBeVisible();
  expect(screen.getByText("占父阶段 99.7%")).toBeVisible();
  expect(screen.getByText("占总耗时 0%")).toBeVisible();
  fireEvent.click(screen.getByText("报告长图渲染与生成"));
  expect(screen.queryByText("Typst 模板与字体检查")).not.toBeInTheDocument();
});

it("旧记录从子阶段汇总 Typst 最大内存，父阶段无需展开编译详情，原始数据保持原样", () => {
  const spans: TraceSpan[] = [
    { span_id: "report", trace_id: "memory", stage_name: "RENDER_REPORT", status: "success", started_at: 1, duration_ms: 1000, payload: { delta_memory_mb: 0.1 } },
    { span_id: "attempt", trace_id: "memory", stage_name: "IMAGE_RENDER_ATTEMPT", status: "success", started_at: 1, duration_ms: 1000, payload: { parent_span_id: "report", service_type: "typst" } },
    ...[250, 150].map((peak, i) => ({ span_id: `compiler-${i}`, trace_id: "memory", stage_name: i ? "TYPST_RECOVERY" : "TYPST_COMPILE", status: "success", started_at: 1, duration_ms: 400, payload: { parent_span_id: "attempt", worker_peak_rss_mb: peak, worker_peak_delta_mb: peak - 20, worker_rss_source: "linux_proc_status" } })),
  ];
  const before = JSON.stringify(spans);
  expect(buildSpanTree(spans)[0].typstMemory).toMatchObject({ typst_peak_rss_mb: 250, typst_peak_delta_mb: 230 });
  expect(JSON.stringify(spans)).toBe(before);
  render(<SpanTimeline spans={spans} totalDurationMs={1000} taskStatus="succeeded" />);
  fireEvent.click(screen.getByText("报告长图渲染与生成"));
  expect(screen.getByText("250 MiB")).toBeVisible();
  expect(screen.getByText("230 MiB")).toBeVisible();
  expect(screen.queryByText("Typst 主题编译")).not.toBeInTheDocument();
});


it("三级轨迹逐层展开，取消状态不显示为失败或成功", () => {
  const spans: TraceSpan[] = [
    { span_id: "report", trace_id: "cancel", stage_name: "RENDER_REPORT", status: "cancelled", started_at: 1, duration_ms: 1000, payload: {} },
    { span_id: "attempt", trace_id: "cancel", stage_name: "IMAGE_RENDER_ATTEMPT", status: "cancelled", started_at: 1, duration_ms: 1000, payload: { parent_span_id: "report", strategy_name: "本地原生" } },
    { span_id: "compile", trace_id: "cancel", stage_name: "TYPST_COMPILE", status: "cancelled", started_at: 1, duration_ms: 1000, payload: { parent_span_id: "attempt", error: "用户取消", cancelled: true } },
  ];
  render(<SpanTimeline spans={spans} totalDurationMs={1000} taskStatus="aborted" />);
  expect(screen.queryByText("Typst 主题编译")).not.toBeInTheDocument();
  fireEvent.click(screen.getByText("报告长图渲染与生成"));
  expect(screen.queryByText("Typst 主题编译")).not.toBeInTheDocument();
  fireEvent.click(screen.getByText(/图片渲染方案尝试/));
  expect(screen.getByText("Typst 主题编译")).toBeVisible();
  expect(screen.getAllByText("已取消 (1.00s)").length).toBeGreaterThan(0);
  expect(screen.queryByText(/失败 \(/)).not.toBeInTheDocument();
});
