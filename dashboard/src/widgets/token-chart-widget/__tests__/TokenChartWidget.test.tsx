import { render, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import type { EChartsOption } from "echarts";
import { TokenChartWidget } from "@/widgets/token-chart-widget/TokenChartWidget";
import type { TokenUsage } from "@/entities/trace/model/types";

let observed: EChartsOption | undefined;
vi.mock("echarts-for-react", () => ({
  default: ({ option }: { option: EChartsOption }) => {
    observed = option;
    return <div data-testid="token-chart" />;
  },
}));
vi.mock("@/shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));
const usage: TokenUsage = {
  trace_id: "demo",
  prompt_tokens: 80,
  completion_tokens: 20,
  total_tokens: 100,
  estimated_cost: 0,
  per_analyzer: {
    topics: { prompt_tokens: 60, completion_tokens: 10, total_tokens: 70 },
    user_titles: { prompt_tokens: 20, completion_tokens: 10, total_tokens: 30 },
    golden_quotes: { prompt_tokens: 0, completion_tokens: 0, total_tokens: 0 },
  },
};
beforeEach(() => {
  observed = undefined;
});

it("缺失记录、已记录零消耗和只有概要总数分别说明，不推断分析模式", () => {
  const view = render(<TokenChartWidget />);
  expect(screen.getByRole("status")).toHaveTextContent("未记录模型用量");
  expect(screen.queryByTestId("token-chart")).not.toBeInTheDocument();
  view.rerender(<TokenChartWidget totalTokens={0} />);
  expect(screen.getByRole("status")).toHaveTextContent("已记录总消耗为 0 Tokens");
  expect(screen.getByText("输入 Tokens").parentElement).toHaveTextContent("未记录");
  view.rerender(<TokenChartWidget totalTokens={42} />);
  expect(screen.getByRole("status")).toHaveTextContent("仅记录了任务总用量");
  expect(screen.getByText("总 Tokens").parentElement).toHaveTextContent("42");
  expect(screen.queryByText(/纯统计模式/)).not.toBeInTheDocument();
});

it("保留输入输出、零消耗模块和完整明细，图表按已记录模块总数比较", () => {
  render(<TokenChartWidget tokenUsage={usage} />);
  const table = screen.getByRole("table");
  expect(within(table).getAllByRole("row")).toHaveLength(4);
  expect(within(table).getByRole("row", { name: "群聊金句 0 0 0" })).toBeVisible();
  expect(within(table).getByRole("row", { name: "话题分析 60 10 70" })).toBeVisible();
  expect(observed?.series).toMatchObject([
    { data: [60, 20], name: "输入 Tokens", stack: "usage", barWidth: 10 },
    { data: [10, 10], name: "输出 Tokens", stack: "usage", barWidth: 10 },
  ]);
  expect(observed?.xAxis).toMatchObject({ show: false, max: "dataMax" });
  expect(observed?.yAxis).toMatchObject({ data: ["话题分析", "群友画像"] });
  expect(screen.queryByText(/与任务总数不同/)).not.toBeInTheDocument();
});

it("记录不一致或非法数值不会改写总量或虚构其他模块", () => {
  const view = render(<TokenChartWidget tokenUsage={{ ...usage, total_tokens: 101 }} />);
  expect(screen.getByRole("status")).toHaveTextContent("模块记录合计 100 Tokens，与任务总数不同");
  expect(screen.getByText("总 Tokens").parentElement).toHaveTextContent("101");
  view.rerender(
    <TokenChartWidget
      tokenUsage={{
        ...usage,
        per_analyzer: {
          broken: { prompt_tokens: NaN, completion_tokens: -1, total_tokens: Infinity },
        },
      }}
    />,
  );
  expect(screen.getByRole("row", { name: "broken 未记录 未记录 未记录" })).toBeVisible();
  expect(screen.queryByTestId("token-chart")).not.toBeInTheDocument();
});

it("使用宿主主题与纯文本图表提示，未知模块名不会作为 HTML 执行", () => {
  document.documentElement.style.setProperty("--chart-input", "rgba(90, 145, 172, 0.58)");
  document.documentElement.style.setProperty("--chart-output", "rgba(149, 122, 177, 0.54)");
  document.documentElement.style.setProperty("--card", "#202020");
  try {
    render(
      <TokenChartWidget
        tokenUsage={{
          ...usage,
          per_analyzer: {
            "<img src=x onerror=alert(1)>": {
              prompt_tokens: 80,
              completion_tokens: 20,
              total_tokens: 100,
            },
          },
        }}
      />,
    );
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeVisible();
    expect(document.querySelector("img")).toBeNull();
    expect(observed).toMatchObject({
      animation: false,
      tooltip: {
        renderMode: "html",
        enterable: false,
        transitionDuration: 0,
        extraCssText: expect.stringContaining("pointer-events: none"),
        confine: true,
        backgroundColor: "#202020",
      },
      series: [
        { itemStyle: { color: "rgba(90, 145, 172, 0.58)" } },
        { itemStyle: { color: "rgba(149, 122, 177, 0.54)" } },
      ],
    });
    const tooltip = observed?.tooltip;
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
        data: 80,
        value: 80,
        $vars: [],
      },
      "",
      () => {},
    );
    expect(content).toBeInstanceOf(HTMLElement);
    if (content instanceof HTMLElement) {
      expect(content.textContent).toContain("<img src=x onerror=alert(1)>");
      expect(content.querySelector("img")).toBeNull();
      expect(content.textContent).toContain("输入 Tokens：80");
    }
  } finally {
    document.documentElement.style.removeProperty("--chart-input");
    document.documentElement.style.removeProperty("--chart-output");
    document.documentElement.style.removeProperty("--card");
  }
});

it("输入输出与模块总数不一致时只画原始总量，不用堆叠伪造用量", () => {
  render(
    <TokenChartWidget
      tokenUsage={{
        ...usage,
        per_analyzer: {
          topics: { prompt_tokens: 60, completion_tokens: 10, total_tokens: 100 },
        },
      }}
    />,
  );
  expect(observed?.series).toMatchObject([{ name: "总 Tokens", data: [100] }]);
  expect(Array.isArray(observed?.series) && observed.series.length).toBe(1);
  expect(screen.getByText("模块总量")).toBeVisible();
  expect(screen.getByRole("row", { name: "话题分析 60 10 100" })).toBeVisible();
});
