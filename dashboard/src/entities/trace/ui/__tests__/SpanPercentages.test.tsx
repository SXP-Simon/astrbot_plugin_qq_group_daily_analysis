import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { SpanTimeline } from "../SpanTimeline";
import type { TraceSpan } from "../../model/types";
import { buildSpanTree } from "../../model/spanTree";

it("实际记录为零的阶段与未记录耗时区分", () => {
  render(
    <SpanTimeline
      spans={[
        {
          span_id: "zero",
          trace_id: "zero",
          stage_name: "FETCH_MESSAGES",
          status: "success",
          started_at: 1,
          duration_ms: 0,
          payload: {},
        },
      ]}
      totalDurationMs={10}
      taskStatus="succeeded"
    />,
  );
  expect(screen.getByText("完成 (0ms)")).toBeVisible();
  expect(screen.getByText("占总耗时 0%")).toBeVisible();
});

it("结束后缺失耗时不显示为零，未知父耗时不能作为占比分母", () => {
  const spans: TraceSpan[] = [
    {
      span_id: "parent",
      trace_id: "unknown",
      stage_name: "RENDER_REPORT",
      status: "success",
      started_at: 1,
      duration_ms: null,
      payload: {},
    },
    {
      span_id: "child",
      trace_id: "unknown",
      stage_name: "TYPST_COMPILE",
      status: "success",
      started_at: 1,
      duration_ms: 10,
      payload: { parent_span_id: "parent" },
    },
  ];
  render(<SpanTimeline spans={spans} taskStatus="succeeded" />);
  fireEvent.click(screen.getByText("报告长图渲染与生成"));
  expect(screen.getByText("完成 (耗时未记录)")).toBeVisible();
  expect(screen.queryByText(/占父阶段/)).not.toBeInTheDocument();
  expect(screen.queryByText(/占总耗时/)).not.toBeInTheDocument();
});

it("缺少当前阶段记录时只提示等待，不伪造阶段和开始时间", () => {
  render(<SpanTimeline spans={[]} currentStage="RENDER_REPORT" taskStatus="running" />);
  expect(screen.getByText(/尚未收到该阶段的详细记录/)).toBeVisible();
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
});

it("默认展开异常子阶段的祖先，切换任务不保留旧选择", () => {
  const parent: TraceSpan = {
    span_id: "parent",
    trace_id: "failure",
    stage_name: "RENDER_REPORT",
    status: "failed",
    started_at: 1,
    duration_ms: 100,
    payload: {},
  };
  const child: TraceSpan = {
    span_id: "child",
    trace_id: "failure",
    stage_name: "TYPST_COMPILE",
    status: "failed",
    started_at: 1,
    duration_ms: 100,
    payload: { parent_span_id: "parent", error: "示例编译错误" },
  };
  const view = render(<SpanTimeline spans={[parent, child]} taskStatus="failed" />);
  expect(screen.getByRole("button", { name: /Typst 主题编译/ })).toHaveAttribute(
    "aria-current",
    "true",
  );
  expect(screen.getByText("示例编译错误")).toBeVisible();
  view.rerender(
    <SpanTimeline
      spans={[{ ...parent, trace_id: "next", status: "skipped" }]}
      taskStatus="skipped"
    />,
  );
  expect(screen.queryByText("示例编译错误")).not.toBeInTheDocument();
  expect(screen.getByText("已跳过 (100ms)")).toBeVisible();
});

it("无法识别的状态不当作成功，运行中耗时不冒充百分之百进度", () => {
  const span: TraceSpan = {
    span_id: "unknown",
    trace_id: "unknown",
    stage_name: "LLM_ANALYSIS",
    status: "unrecognized",
    started_at: 1,
    duration_ms: null,
    payload: {},
  };
  const view = render(<SpanTimeline spans={[span]} taskStatus="failed" />);
  expect(screen.getByText("状态未记录 (耗时未记录)")).toBeVisible();
  view.rerender(
    <SpanTimeline
      spans={[{ ...span, status: "running", started_at: Date.now() / 1000 - 2 }]}
      taskStatus="running"
    />,
  );
  expect(screen.getByText(/执行中 \(已运行/)).toBeVisible();
  expect(screen.queryByText(/100%/)).not.toBeInTheDocument();
  expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
});

it("父阶段占任务总耗时，子阶段相对父阶段计算，短步骤不再抬高到2%", () => {
  const spans: TraceSpan[] = [
    {
      span_id: "render",
      trace_id: "test",
      stage_name: "RENDER_REPORT",
      status: "success",
      started_at: 1,
      duration_ms: 1000,
      payload: {},
    },
    {
      span_id: "validate",
      trace_id: "test",
      stage_name: "TYPST_VALIDATE",
      status: "success",
      started_at: 1,
      duration_ms: 3,
      payload: { parent_span_id: "render" },
    },
    {
      span_id: "compile",
      trace_id: "test",
      stage_name: "TYPST_COMPILE",
      status: "success",
      started_at: 1.003,
      duration_ms: 997,
      payload: { parent_span_id: "render" },
    },
    {
      span_id: "old",
      trace_id: "test",
      stage_name: "SAVE_SUMMARY",
      status: "success",
      started_at: 2,
      duration_ms: 0,
      payload: { parent_span_id: "missing" },
    },
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
    {
      span_id: "report",
      trace_id: "memory",
      stage_name: "RENDER_REPORT",
      status: "success",
      started_at: 1,
      duration_ms: 1000,
      payload: { delta_memory_mb: 0.1 },
    },
    {
      span_id: "attempt",
      trace_id: "memory",
      stage_name: "IMAGE_RENDER_ATTEMPT",
      status: "success",
      started_at: 1,
      duration_ms: 1000,
      payload: { parent_span_id: "report", service_type: "typst" },
    },
    ...[250, 150].map((peak, i) => ({
      span_id: `compiler-${i}`,
      trace_id: "memory",
      stage_name: i ? "TYPST_RECOVERY" : "TYPST_COMPILE",
      status: "success",
      started_at: 1,
      duration_ms: 400,
      payload: {
        parent_span_id: "attempt",
        worker_peak_rss_mb: peak,
        worker_peak_delta_mb: peak - 20,
        worker_rss_source: "linux_proc_status",
      },
    })),
  ];
  const before = JSON.stringify(spans);
  expect(buildSpanTree(spans)[0].typstMemory).toMatchObject({
    typst_peak_rss_mb: 250,
    typst_peak_delta_mb: 230,
  });
  expect(JSON.stringify(spans)).toBe(before);
  render(<SpanTimeline spans={spans} totalDurationMs={1000} taskStatus="succeeded" />);
  fireEvent.click(screen.getByText("报告长图渲染与生成"));
  expect(screen.getByText("250 MiB")).toBeVisible();
  expect(screen.getByText("230 MiB")).toBeVisible();
  expect(screen.queryByText("Typst 主题编译")).not.toBeInTheDocument();
});

it("三级轨迹逐层展开，取消状态不显示为失败或成功", () => {
  const spans: TraceSpan[] = [
    {
      span_id: "report",
      trace_id: "cancel",
      stage_name: "RENDER_REPORT",
      status: "cancelled",
      started_at: 1,
      duration_ms: 1000,
      payload: {},
    },
    {
      span_id: "attempt",
      trace_id: "cancel",
      stage_name: "IMAGE_RENDER_ATTEMPT",
      status: "cancelled",
      started_at: 1,
      duration_ms: 1000,
      payload: { parent_span_id: "report", strategy_name: "本地原生" },
    },
    {
      span_id: "compile",
      trace_id: "cancel",
      stage_name: "TYPST_COMPILE",
      status: "cancelled",
      started_at: 1,
      duration_ms: 1000,
      payload: { parent_span_id: "attempt", error: "用户取消", cancelled: true },
    },
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
