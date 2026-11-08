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

it("悬浮提示用语义色和系列色标记分行数据，保留零值并拒绝越界记录", () => {
  const data = createMockAnalyticsTrends();
  const point = { ...data.points[0], failed_count: 0 };
  const colors = {
    text: "#111111",
    muted: "#666666",
    border: "#dddddd",
    background: "#ffffff",
    accent: "rgb(50, 80, 110)",
    input: "rgb(20, 100, 150)",
    output: "rgb(150, 100, 180)",
    success: "rgb(40, 120, 70)",
    danger: "rgb(180, 50, 40)",
    providerColors: ["#123456"],
  };
  const options = createOverviewTrendOptions([point], [], colors);
  for (const [index, labels, markers, values] of [
    [
      0,
      ["分析", "成功", "失败"],
      [colors.accent, colors.success, colors.danger],
      [`${point.request_count} 次`, `${point.succeeded_count} 次`, "0 次"],
    ],
    [
      1,
      ["总消耗", "输入", "输出"],
      [colors.accent, colors.input, colors.output],
      [
        `${point.total_tokens.toLocaleString()} Tokens`,
        point.prompt_tokens.toLocaleString(),
        point.completion_tokens.toLocaleString(),
      ],
    ],
  ] as const) {
    const tooltip = options[index].tooltip;
    if (!tooltip || Array.isArray(tooltip) || typeof tooltip.formatter !== "function")
      throw new Error("趋势提示格式化函数缺失");
    const params = {
      componentType: "series",
      componentSubType: "line",
      componentIndex: 0,
      $vars: [],
      seriesType: "line",
      seriesIndex: 0,
      name: point.date_full,
      dataIndex: 0,
      data: 0,
      value: 0,
    };
    const content = tooltip.formatter(params, "test", () => {});
    if (!(content instanceof HTMLElement)) throw new Error("提示内容不是文本容器");
    expect(content.children[0]).toHaveTextContent(point.date_full);
    for (let row = 0; row < 3; row++) {
      const line = content.children[row + 1];
      expect(line.children[1]).toHaveTextContent(labels[row]);
      expect(line.children[2]).toHaveTextContent(values[row]);
      expect(line.querySelector<HTMLElement>("[aria-hidden=true]")?.style.backgroundColor).toBe(
        markers[row],
      );
    }
    expect(tooltip.formatter({ ...params, dataIndex: 99 }, "test", () => {})).toBe("");
  }
});

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
    expect(options[1].series).toMatchObject([
      { name: "输入", itemStyle: { color: colors.accent } },
      { name: "输出", itemStyle: { color: colors.providerColors[1] } },
    ]);
    const custom = createOverviewTrendOptions(data.points, data.provider_breakdown, {
      ...colors,
      input: "#4f7fd9",
      output: "#a18ad1",
    });
    expect(custom[1].series).toMatchObject([
      { name: "输入", itemStyle: { color: "#4f7fd9" } },
      { name: "输出", itemStyle: { color: "#a18ad1" } },
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

it("组件读取宿主主辅色变量传入输入输出系列，图例沿用系列颜色", () => {
  document.documentElement.style.setProperty("--chart-trend-input", "#123456");
  document.documentElement.style.setProperty("--chart-trend-output", "#987654");
  try {
    render(<OverviewTrendCharts initialTrends={createMockAnalyticsTrends()} />);
    expect(
      chartRender.mock.calls.some(([option]) => {
        const series = option.series;
        return (
          Array.isArray(series) &&
          series[0]?.name === "输入" &&
          series[0].itemStyle.color === "#123456" &&
          series[1].itemStyle.color === "#987654"
        );
      }),
    ).toBe(true);
  } finally {
    document.documentElement.style.removeProperty("--chart-trend-input");
    document.documentElement.style.removeProperty("--chart-trend-output");
  }
});

it("默认混合色经过浏览器转换后传给图表，不依赖 Mock 的宿主 RGB 覆盖", () => {
  vi.stubGlobal("CSS", { supports: () => true });
  const canvas = vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue({
    fillRect: vi.fn(),
    getImageData: () => ({ data: new Uint8ClampedArray([30, 75, 101, 255]) }),
  } as unknown as CanvasRenderingContext2D);
  document.documentElement.style.setProperty("--ring", "color-mix(in srgb, #3c96ca 50%, #000)");
  document.documentElement.style.setProperty(
    "--chart-trend-input",
    "color-mix(in srgb, #3c96ca 50%, #000)",
  );
  try {
    render(<OverviewTrendCharts initialTrends={createMockAnalyticsTrends()} />);
    const line = chartRender.mock.calls.find(([option]) => option.series[0]?.type === "line")?.[0];
    const bars = chartRender.mock.calls.find(([option]) => option.series[0]?.type === "bar")?.[0];
    const pie = chartRender.mock.calls.find(([option]) => option.series[0]?.type === "pie")?.[0];
    expect(line?.series[0].lineStyle.color).toBe("rgba(30, 75, 101, 1)");
    expect(bars?.series[0].itemStyle.color).toBe("rgba(30, 75, 101, 1)");
    expect(pie?.series[0].data[0].itemStyle.color).toBe("rgba(30, 75, 101, 1)");
  } finally {
    document.documentElement.style.removeProperty("--ring");
    document.documentElement.style.removeProperty("--chart-trend-input");
    canvas.mockRestore();
    vi.unstubAllGlobals();
  }
});
