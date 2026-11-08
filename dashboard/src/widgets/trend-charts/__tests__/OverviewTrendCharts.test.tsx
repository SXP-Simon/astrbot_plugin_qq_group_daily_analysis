import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OverviewTrendCharts } from "../OverviewTrendCharts";
import { fetchAnalyticsTrends } from "../../../entities/metric/api/metricApi";
import { createMockAnalyticsTrends } from "../../../mocks/data/metrics";
import { createOverviewTrendOptions } from "../overviewTrendOptions";

const chartRender = vi.hoisted(() => vi.fn());
vi.mock("echarts-for-react", () => ({
  default: ({ option }: { option: unknown }) => {
    chartRender(option);
    return <div data-testid="chart" />;
  },
}));
vi.mock("../../../entities/metric/api/metricApi", () => ({ fetchAnalyticsTrends: vi.fn() }));
vi.mock("../../../shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));
beforeEach(() => vi.resetAllMocks());

describe("趋势图与明细", () => {
  it("零数据不借用历史总量，保留每个时间点和全部服务商明细", () => {
    const data = createMockAnalyticsTrends();
    const empty = {
      ...data,
      points: data.points.map((point) => ({
        ...point,
        request_count: 0,
        succeeded_count: 0,
        failed_count: 0,
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: 0,
      })),
      provider_breakdown: [{ name: "零消耗示例", request_count: 1, total_tokens: 0 }],
    };
    render(<OverviewTrendCharts initialTrends={empty} totalTraces={999} totalTokens={999999} />);
    expect(screen.getByText("0 次")).toBeVisible();
    expect(screen.getByText("0 Tokens")).toBeVisible();
    fireEvent.click(screen.getByText("查看趋势明细"));
    expect(
      within(screen.getByRole("region", { name: "趋势明细" })).getAllByRole("row"),
    ).toHaveLength(15);
    fireEvent.click(screen.getByText("查看服务商明细"));
    expect(
      within(screen.getByRole("region", { name: "服务商明细" })).getByText("零消耗示例"),
    ).toBeVisible();
    expect(screen.getByText("暂无消耗记录")).toBeVisible();
    expect(screen.getByText("未记录消耗")).toBeVisible();
    expect(screen.queryByText("999 次")).not.toBeInTheDocument();
  });

  it("范围切换失败显示实际保留的范围，并能从按钮重试", async () => {
    vi.mocked(fetchAnalyticsTrends)
      .mockRejectedValueOnce(new Error("离线"))
      .mockResolvedValueOnce(createMockAnalyticsTrends("day", 7));
    render(
      <OverviewTrendCharts
        initialTrends={createMockAnalyticsTrends()}
        totalTraces={142}
        totalTokens={333700}
      />,
    );
    fireEvent.change(screen.getByRole("combobox", { name: "趋势时间范围" }), {
      target: { value: "7d" },
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("检查连接");
    expect(screen.getByText("当前保留的是近14天的数据。")).toBeVisible();
    await act(async () => fireEvent.click(screen.getByRole("button", { name: "刷新趋势" })));
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByText("近7天 · 分析次数与模型消耗")).toBeInTheDocument();
  });

  it("图表使用主题颜色，提示浮层不拦截鼠标且不解析渠道名中的 HTML", () => {
    const data = createMockAnalyticsTrends();
    const colors = {
      text: "#111",
      muted: "#666",
      border: "#ddd",
      background: "#fff",
      accent: "#abc",
      providerColors: ["#abc", "#def"],
    };
    const options = createOverviewTrendOptions(data.points, data.provider_breakdown, colors);
    for (const option of options) {
      expect(option.animation).toBe(false);
      expect(option.tooltip).toMatchObject({
        renderMode: "html",
        enterable: false,
        transitionDuration: 0,
        extraCssText: expect.stringContaining("pointer-events: none"),
        confine: true,
        backgroundColor: colors.background,
      });
      expect(option.textStyle).toMatchObject({ color: colors.text });
    }
    expect(options[0].series).toMatchObject([
      { data: data.points.map((point) => point.request_count) },
    ]);
    expect(options[1].series).toMatchObject([
      { name: "输入", data: data.points.map((point) => point.prompt_tokens) },
      { name: "输出", data: data.points.map((point) => point.completion_tokens) },
    ]);
    expect(options[1].aria).toMatchObject({
      enabled: true,
      label: {
        description: `模型消耗堆叠柱图，${data.points.length} 个时间点。输入 ${data.points.reduce((sum, point) => sum + point.prompt_tokens, 0).toLocaleString()} Tokens，输出 ${data.points.reduce((sum, point) => sum + point.completion_tokens, 0).toLocaleString()} Tokens。完整数值见下方趋势明细。`,
      },
    });
    for (const option of options) {
      expect(option.aria?.label?.description).toBeTruthy();
      expect(option.aria?.label?.description).not.toMatch(/NaN|undefined/);
    }
    expect(options[2].series).toMatchObject([
      {
        type: "pie",
        stillShowZeroSum: false,
        data: data.provider_breakdown.map((item) => ({
          name: item.name,
          value: item.total_tokens,
        })),
      },
    ]);
    const name = '<img src=x onerror="alert(1)">渠道 & 测试';
    const [, , providerOption] = createOverviewTrendOptions(
      data.points,
      [{ name, total_tokens: 1200, request_count: 3 }],
      colors,
    );
    const tooltip = providerOption.tooltip;
    if (!tooltip || Array.isArray(tooltip) || typeof tooltip.formatter !== "function")
      throw new Error("服务商提示格式化函数缺失");
    const content = tooltip.formatter(
      {
        componentType: "series",
        componentSubType: "pie",
        componentIndex: 0,
        $vars: ["seriesName", "name", "value", "percent"],
        seriesType: "pie",
        seriesIndex: 0,
        name,
        dataIndex: 0,
        data: 1200,
        value: 1200,
      },
      "test",
      () => {},
    );
    expect(content).toBeInstanceOf(HTMLElement);
    if (!(content instanceof HTMLElement)) throw new Error("提示内容不是文本容器");
    expect(content.textContent).toBe(`${name}\n1,200 Tokens · 100.0%\n分析 3 次`);
    expect(content.childElementCount).toBe(0);
  });

  it("父页更新任务耗时不会重设图表，真正的趋势变更仍刷新", () => {
    const data = createMockAnalyticsTrends();
    const { rerender } = render(<OverviewTrendCharts initialTrends={data} />);
    const initialRenders = chartRender.mock.calls.length;
    for (let tick = 0; tick < 4; tick++) rerender(<OverviewTrendCharts initialTrends={data} />);
    expect(chartRender).toHaveBeenCalledTimes(initialRenders);
    const changed = {
      ...data,
      points: data.points.map((point) => ({ ...point, request_count: point.request_count + 1 })),
    };
    rerender(<OverviewTrendCharts initialTrends={changed} />);
    expect(chartRender.mock.calls.length).toBeGreaterThan(initialRenders);
    expect(
      screen.getByText(`${changed.points.reduce((sum, point) => sum + point.request_count, 0)} 次`),
    ).toBeVisible();
  });
});

it("多渠道显示前六名与聚合占比，全部长名称和数值仍可在明细读取", () => {
  const providers = Array.from({ length: 12 }, (_, index) => ({
    name: `示例渠道 ${index} / 一个很长的自定义服务商名称`,
    total_tokens: (12 - index) * 100,
    request_count: 1,
  }));
  render(
    <OverviewTrendCharts
      initialTrends={{ ...createMockAnalyticsTrends(), provider_breakdown: providers }}
    />,
  );
  const legend = screen.getByRole("list", { name: "服务商占比图例" });
  expect(within(legend).getAllByRole("listitem")).toHaveLength(7);
  expect(within(legend).getByText("其他服务商（6个）")).toBeVisible();
  expect(within(legend).getByText("26.9%")).toBeVisible();
  expect(within(legend).getByText(providers[0].name)).toHaveAttribute(
    "title",
    expect.stringContaining("1,200 Tokens"),
  );
  fireEvent.click(screen.getByText("查看服务商明细"));
  const table = screen.getByRole("region", { name: "服务商明细" });
  expect(within(table).getAllByRole("row")).toHaveLength(13);
  expect(within(table).getByText(providers[11].name)).toBeVisible();
});
