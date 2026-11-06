import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { TraceMetricsChart } from "../TraceMetricsChart";
import { mockTypstTraces } from "../../../../mocks/data/typstTraces";
import type { TraceRecord } from "../../model/types";

vi.mock("echarts-for-react", () => ({
  default: ({ option }: { option: { yAxis?: { data?: string[] } } }) => (
    <pre data-testid="chart-categories">{JSON.stringify(option.yAxis?.data || [])}</pre>
  ),
}));
vi.mock("../../../../shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));

it("不同引擎尝试在精简图中均保留，不被按同名阶段折叠或误计重试", () => {
  render(
    <TraceMetricsChart
      trace={mockTypstTraces.find((trace) => trace.trace_id === "trace-typst-fallback")!}
    />,
  );
  const categories = screen.getByTestId("chart-categories").textContent || "";
  expect(categories.match(/图片渲染方案尝试/g)).toHaveLength(2);
  expect(categories).toContain("Typst 主题编译");
  expect(categories).toContain("HTML 图片服务渲染");
  expect(screen.queryByText(/重试损耗/)).not.toBeInTheDocument();
});

it("重试父阶段时精简图连同旧子树一起过滤，全量图仍可查看", () => {
  const trace: TraceRecord = {
    trace_id: "retry",
    group_id: "demo",
    group_name: "demo",
    platform: "aiocqhttp",
    trigger_type: "web_ui",
    status: "succeeded",
    started_at: 1,
    duration_ms: 40,
    spans: [
      {
        span_id: "old",
        trace_id: "retry",
        stage_name: "RENDER_REPORT",
        status: "failed",
        started_at: 1,
        duration_ms: 20,
        payload: {},
      },
      {
        span_id: "old-child",
        trace_id: "retry",
        stage_name: "TYPST_RESOURCES",
        status: "failed",
        started_at: 1,
        duration_ms: 20,
        payload: { parent_span_id: "old" },
      },
      {
        span_id: "new",
        trace_id: "retry",
        stage_name: "RENDER_REPORT",
        status: "success",
        started_at: 1.02,
        duration_ms: 20,
        payload: {},
      },
      {
        span_id: "new-child",
        trace_id: "retry",
        stage_name: "TYPST_VALIDATE",
        status: "success",
        started_at: 1.02,
        duration_ms: 20,
        payload: { parent_span_id: "new" },
      },
    ],
  };
  render(<TraceMetricsChart trace={trace} />);
  expect(screen.getByTestId("chart-categories")).not.toHaveTextContent("Typst 本地素材与下载");
  fireEvent.click(screen.getByText(/全量重试/));
  expect(screen.getByTestId("chart-categories")).toHaveTextContent("Typst 本地素材与下载");
});
