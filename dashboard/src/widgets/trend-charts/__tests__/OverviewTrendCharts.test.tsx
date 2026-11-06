import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { OverviewTrendCharts } from "../OverviewTrendCharts";
import { fetchAnalyticsTrends } from "../../../entities/metric/api/metricApi";
import { createMockAnalyticsTrends } from "../../../mocks/data/metrics";
import { createOverviewTrendOptions } from "../overviewTrendOptions";

vi.mock("echarts-for-react", () => ({ default: () => <div data-testid="chart" /> }));
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
    expect(screen.getByText("零消耗示例")).toBeVisible();
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

  it("图表使用主题颜色和纯文本提示，无动画或 HTML 拼接", () => {
    const data = createMockAnalyticsTrends();
    const colors = {
      text: "#111",
      muted: "#666",
      border: "#ddd",
      background: "#fff",
      accent: "#abc",
    };
    const options = createOverviewTrendOptions(data.points, data.provider_breakdown, colors);
    for (const option of options) {
      expect(option.animation).toBe(false);
      expect(option.tooltip).toMatchObject({
        renderMode: "richText",
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
    expect(options[2].series).toMatchObject([
      { data: data.provider_breakdown.map((item) => item.total_tokens) },
    ]);
  });
});
