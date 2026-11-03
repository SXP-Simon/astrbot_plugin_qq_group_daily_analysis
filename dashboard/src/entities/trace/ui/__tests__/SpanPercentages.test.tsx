import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";
import { SpanTimeline } from "../SpanTimeline";
import type { TraceSpan } from "../../model/types";

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
  expect(screen.getByText("占父阶段 0.3%")).toBeVisible();
  expect(screen.getByText("占父阶段 99.7%")).toBeVisible();
  expect(screen.getByText("占总耗时 0%")).toBeVisible();
});
