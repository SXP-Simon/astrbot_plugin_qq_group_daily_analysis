import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { AnalysisRuntimePanel } from "@/widgets/analysis-runtime/ui/AnalysisRuntimePanel";
import { mockMetricsSummary } from "@/mocks/data/metrics";

it("展示实测耗时和紧凑熔断状态，并跳转到对应配置分组", () => {
  const open = vi.fn();
  render(
    <AnalysisRuntimePanel
      metrics={mockMetricsSummary}
      loading={false}
      onRetry={vi.fn()}
      error=""
      onOpenConfig={open}
    />,
  );
  const list = screen.getByRole("list", { name: "最近成功分析耗时" });
  const [latest, ...previous] = within(list).getAllByRole("listitem");
  expect(latest).toHaveTextContent("最新一次18.20s");
  expect(previous.map((item) => item.textContent)).toEqual(["11.38s", "12.06s", "9.84s", "10.75s"]);
  expect(screen.getByText("1 冷却 · 1 待恢复")).toBeVisible();
  expect(screen.getByText("等待恢复尝试")).toBeVisible();
  expect(screen.getByText("38 秒")).toHaveTextContent("读取时剩余 38 秒");
  fireEvent.click(screen.getByRole("button", { name: "并发限流设置" }));
  expect(open).toHaveBeenLastCalledWith("performance");
  fireEvent.click(screen.getByRole("button", { name: "LLM 设置" }));
  expect(open).toHaveBeenLastCalledWith("llm");
});

it("刷新后更新展示；无数据与读取失败不伪装成健康或零耗时", () => {
  const props = { onOpenConfig: vi.fn(), onRetry: vi.fn(), error: "", loading: false };
  const view = render(<AnalysisRuntimePanel {...props} metrics={null} loading />);
  expect(screen.getByText("正在读取运行状态…")).toBeVisible();
  expect(screen.queryByText("暂无记录")).not.toBeInTheDocument();
  view.rerender(<AnalysisRuntimePanel {...props} metrics={null} error="读取失败" />);
  fireEvent.click(screen.getByRole("button", { name: "重试" }));
  expect(props.onRetry).toHaveBeenCalledOnce();
  expect(screen.queryByText("暂无记录")).not.toBeInTheDocument();
  view.rerender(<AnalysisRuntimePanel {...props} metrics={mockMetricsSummary} loading />);
  expect(screen.getByText("更新中")).toBeVisible();
  expect(screen.getByText("18.20s")).toBeVisible();
  view.rerender(<AnalysisRuntimePanel {...props} metrics={mockMetricsSummary} />);
  expect(screen.getByText("冷却中")).toBeVisible();
  const recovered = {
    ...mockMetricsSummary,
    llm_runtime: {
      captured_at: Date.now() / 1000,
      circuits: {
        primary: {
          state: "CLOSED" as const,
          failure_count: 0,
          failure_threshold: 5,
          recovery_timeout_seconds: 60,
          retry_after_seconds: 0,
        },
      },
    },
  };
  view.rerender(<AnalysisRuntimePanel {...props} metrics={recovered} error="读取失败" />);
  expect(screen.getByText("未熔断")).toBeVisible();
  expect(screen.queryByText("冷却中")).not.toBeInTheDocument();
  expect(screen.getByText("更新失败，以下为上次读取结果")).toBeVisible();
  view.rerender(
    <AnalysisRuntimePanel
      {...props}
      metrics={{
        ...recovered,
        analysis_performance: { recent_durations_ms: [] },
        llm_runtime: { captured_at: 1, circuits: {} },
      }}
    />,
  );
  expect(screen.getByText("本次运行还没有模型调用记录。")).toBeVisible();
  expect(screen.getByText("暂无记录")).toBeVisible();
});

it("成功记录不足五条时只展示已有的实际耗时", () => {
  render(
    <AnalysisRuntimePanel
      metrics={{
        ...mockMetricsSummary,
        analysis_performance: { recent_durations_ms: [18200, 11380] },
      }}
      error=""
      onOpenConfig={vi.fn()}
      onRetry={vi.fn()}
      loading={false}
    />,
  );
  const list = screen.getByRole("list", { name: "最近成功分析耗时" });
  expect(within(list).getAllByRole("listitem")).toHaveLength(2);
  expect(within(list).getByText("18.20s")).toBeVisible();
  expect(within(list).getByText("11.38s")).toBeVisible();
});
