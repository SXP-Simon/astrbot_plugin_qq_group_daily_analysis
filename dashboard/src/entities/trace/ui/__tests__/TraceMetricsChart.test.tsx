import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { TraceMetricsChart } from "@/entities/trace/ui/TraceMetricsChart";
import { mockTypstTraces } from "@/mocks/data/typstTraces";
import type { TraceRecord } from "@/entities/trace/model/types";
import { getTraceMetrics } from "@/entities/trace/model/traceMetrics";
import { createTraceMetricsOption } from "@/entities/trace/ui/traceMetricsOption";

vi.mock("echarts-for-react", () => ({
  default: ({ option }: { option: { yAxis?: { data?: string[] } } }) => (
    <pre data-testid="chart-categories">{JSON.stringify(option.yAxis?.data || [])}</pre>
  ),
}));
vi.mock("@/shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));

it("保留三类图表与数据查看，未知耗时不成为零或累计总耗时", () => {
  render(
    <TraceMetricsChart
      trace={{
        trace_id: "missing",
        group_id: "example",
        group_name: "示例",
        platform: "satori",
        trigger_type: "manual",
        status: "succeeded",
        started_at: 1,
        spans: [
          {
            trace_id: "missing",
            span_id: "unknown",
            stage_name: "FETCH_MESSAGES",
            started_at: 1,
            status: "success",
            duration_ms: null,
            payload: {},
          },
          {
            trace_id: "missing",
            span_id: "zero",
            stage_name: "CLEAN_MESSAGES",
            started_at: 1,
            status: "success",
            duration_ms: 0,
            payload: {},
          },
        ],
      }}
    />,
  );
  expect(screen.getByText("记录总耗时：未记录")).toBeVisible();
  fireEvent.click(screen.getByText("查看图表数据"));
  const table = screen.getByRole("table", { name: "阶段耗时记录" });
  expect(within(table).getByText("未记录")).toBeVisible();
  expect(within(table).getByText("0 ms")).toBeVisible();
  fireEvent.mouseDown(screen.getByRole("tab", { name: "宿主 RSS 采样" }), {
    button: 0,
    ctrlKey: false,
  });
  expect(screen.getByText("没有对应的采样记录")).toBeVisible();
  fireEvent.mouseDown(screen.getByRole("tab", { name: "传输体积" }), { button: 0, ctrlKey: false });
  expect(screen.getByText(/没有记录不代表未生成报告/)).toBeVisible();
});

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

it("任务指标提示不拦截鼠标，阶段名称按纯文本显示", () => {
  const metrics = getTraceMetrics(
    {
      ...mockTypstTraces[0],
      spans: [
        {
          trace_id: "hover",
          span_id: "render",
          stage_name: "RENDER_REPORT",
          status: "success",
          started_at: 1,
          duration_ms: 200,
          payload: { strategy_name: "<img src=x onerror=alert(1)>" },
        },
      ],
    },
    "all",
  );
  const option = createTraceMetricsOption(metrics, "duration", {
    text: "#111111",
    muted: "#666666",
    background: "#ffffff",
    border: "#dddddd",
    accent: "rgb(30, 75, 101)",
    danger: "#bb2222",
  });
  expect(option.tooltip).toMatchObject({
    renderMode: "html",
    enterable: false,
    transitionDuration: 0,
    extraCssText: expect.stringContaining("pointer-events: none"),
  });
  const tooltip = option.tooltip;
  if (!tooltip || Array.isArray(tooltip) || typeof tooltip.formatter !== "function")
    throw new Error("缺少提示格式化函数");
  const content = tooltip.formatter(
    {
      componentType: "series",
      componentSubType: "bar",
      componentIndex: 0,
      seriesIndex: 0,
      seriesType: "bar",
      name: "",
      dataIndex: 0,
      data: 200,
      value: 200,
      $vars: [],
    },
    "",
    () => {},
  );
  expect(content).toBeInstanceOf(HTMLElement);
  if (content instanceof HTMLElement) {
    expect(content.textContent).toContain("<img src=x onerror=alert(1)>");
    expect(content.textContent).toContain("200 ms");
    expect(content.querySelector("img")).toBeNull();
  }
});
