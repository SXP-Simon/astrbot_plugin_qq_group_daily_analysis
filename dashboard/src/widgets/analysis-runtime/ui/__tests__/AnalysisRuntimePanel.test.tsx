import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { AnalysisRuntimePanel } from "@/widgets/analysis-runtime/ui/AnalysisRuntimePanel";
import { mockMetricsSummary } from "@/mocks/data/metrics";

it("展示实测耗时和紧凑熔断状态，并跳转到对应配置分组", () => {
  const open = vi.fn();
  render(<AnalysisRuntimePanel metrics={mockMetricsSummary} error="" onOpenConfig={open} />);
  expect(screen.getByText("12.45s")).toBeVisible();
  expect(screen.getByText("18.20s")).toBeVisible();
  expect(screen.getByText("1 冷却 · 1 待恢复")).toBeVisible();
  expect(screen.getByText("等待恢复尝试")).toBeVisible();
  expect(screen.getByText("读取时剩余 38 秒")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "并发限流设置" }));
  expect(open).toHaveBeenLastCalledWith("performance");
  fireEvent.click(screen.getByRole("button", { name: "LLM 设置" }));
  expect(open).toHaveBeenLastCalledWith("llm");
});

it("刷新后更新展示；无数据与读取失败不伪装成健康或零耗时", () => {
  const props = { onOpenConfig: vi.fn(), error: "" };
  const view = render(<AnalysisRuntimePanel {...props} metrics={null} />);
  expect(screen.getByText("未读取")).toBeVisible();
  expect(screen.getAllByText("暂无记录")).toHaveLength(2);
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
      metrics={{ ...recovered, llm_runtime: { captured_at: 1, circuits: {} } }}
    />,
  );
  expect(screen.getByText("本次运行还没有模型调用记录。")).toBeVisible();
});
