import { expect, it, vi } from "vitest";
import { waitFor } from "@testing-library/react";
import { init } from "echarts";
import { createOverviewTrendOptions } from "../overviewTrendOptions";
import { createMockAnalyticsTrends } from "../../../mocks/data/metrics";

it.each([0, 1, 2])("真实 SVG 图表反复高亮和取消后仍保留图形颜色：%s", async (index) => {
  const data = createMockAnalyticsTrends();
  // 与浏览器转换默认混合色后的结果一致，不以 Mock 的显式宿主配色代替。
  const colors = {
    text: "#ffffff",
    muted: "#aaaaaa",
    border: "#444444",
    background: "#151515",
    accent: "rgba(30, 75, 101, 1)",
    input: "rgba(30, 75, 101, 1)",
    output: "rgba(47, 134, 189, 0.62)",
    providerColors: ["rgba(30, 75, 101, 1)", "rgba(47, 134, 189, 0.62)"],
  };
  const option = createOverviewTrendOptions(data.points, data.provider_breakdown, colors)[index];
  const canvas = vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  const container = document.createElement("div");
  document.body.append(container);
  const chart = init(container, undefined, { renderer: "svg", width: 360, height: 230 });
  try {
    chart.setOption(option);
    const normal = container.innerHTML;
    expect(normal).toContain("rgb(30,75,101)");
    for (let attempt = 0; attempt < 3; attempt++) {
      chart.dispatchAction({ type: "highlight", seriesIndex: 0, dataIndex: 0 });
      chart.getZr().flush();
      // 等待真实图表的状态更新帧；SSR 不执行鼠标高亮状态，不能代替此验证。
      await waitFor(() => expect(container.innerHTML).toContain("rgb(33,82,111)"));
      expect(container.innerHTML).not.toMatch(/(?:undefined|NaN|color-mix)/);
      chart.dispatchAction({ type: "downplay", seriesIndex: 0, dataIndex: 0 });
      chart.getZr().flush();
      await waitFor(() => expect(container.innerHTML).toContain("rgb(30,75,101)"));
    }
  } finally {
    chart.dispose();
    container.remove();
    canvas.mockRestore();
  }
});
