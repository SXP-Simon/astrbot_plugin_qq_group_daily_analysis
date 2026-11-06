import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { OverviewPage } from "../OverviewPage";
import type { useOverviewViewModel } from "../../model/useOverviewViewModel";
import { mockMetricsSummary } from "../../../../mocks/data/metrics";
import { mockActiveTasks } from "../../../../mocks/data/tasks";
import { mockTraces } from "../../../../mocks/data/traces";

vi.mock("../../../../widgets/trend-charts/OverviewTrendCharts", () => ({
  OverviewTrendCharts: () => <div>趋势图区域</div>,
}));
function viewModel(): ReturnType<typeof useOverviewViewModel> {
  return {
    metrics: mockMetricsSummary,
    activeTasks: mockActiveTasks.slice(0, 2),
    recentTraces: [],
    attentionTraces: [],
    loading: false,
    tasksLoaded: true,
    errors: { tasks: "", metrics: "", recent: "" },
    feedback: "",
    refresh: vi.fn().mockResolvedValue(undefined),
    handleSSEEvent: vi.fn(),
    handleCancelTask: vi.fn().mockResolvedValue(false),
  };
}

describe("总览页面", () => {
  it("并行任务和问题在统计之前；诊断、中止和发起入口保持可用", async () => {
    const vm = viewModel();
    vm.attentionTraces = [
      {
        ...mockTraces[0],
        trace_id: "failed-task",
        status: "failed",
        error_message: "服务请求超时",
      },
    ];
    const onViewTrace = vi.fn();
    const onOpenTrigger = vi.fn();
    render(<OverviewPage viewModel={vm} onViewTrace={onViewTrace} onOpenTrigger={onOpenTrigger} />);
    const headings = screen.getAllByRole("heading", { level: 2 }).map((node) => node.textContent);
    expect(headings).toEqual(["正在执行中的分析任务 2 运行中", "需要关注", "分析统计"]);
    expect(screen.getByText("趋势图区域")).toBeVisible();
    expect(screen.getByText("今日模型消耗")).toBeVisible();
    expect(screen.getByText("近30天模型消耗")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "查看过程" }));
    expect(onViewTrace).toHaveBeenCalledWith("failed-task");
    fireEvent.click(screen.getByRole("button", { name: "发起分析" }));
    expect(onOpenTrigger).toHaveBeenCalledOnce();
    fireEvent.click(screen.getAllByRole("button", { name: "中止" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "确认中止" }));
    expect(await within(screen.getByRole("dialog")).findByRole("alert")).toHaveTextContent(
      "中止请求未成功",
    );
    expect(vm.handleCancelTask).toHaveBeenCalledWith(mockActiveTasks[0].task_id);
  });

  it("未加载或失败时不声称没有任务、没有异常，也不编造零统计", () => {
    const vm = {
      ...viewModel(),
      metrics: null,
      activeTasks: [],
      tasksLoaded: false,
      errors: { tasks: "任务读取失败", metrics: "统计读取失败", recent: "近期记录读取失败" },
    };
    const { rerender } = render(
      <OverviewPage viewModel={vm} onViewTrace={vi.fn()} onOpenTrigger={vi.fn()} />,
    );
    expect(screen.getAllByText("未读取")).toHaveLength(7);
    expect(screen.queryByText("暂无正在执行的后台分析任务")).not.toBeInTheDocument();
    expect(screen.queryByText("近期记录中没有失败或警告")).not.toBeInTheDocument();
    expect(screen.getAllByRole("alert")).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: "重新加载" }));
    expect(vm.refresh).toHaveBeenCalledWith(false);
    rerender(
      <OverviewPage
        viewModel={{ ...vm, tasksLoaded: true, errors: { tasks: "", metrics: "", recent: "" } }}
        onViewTrace={vi.fn()}
        onOpenTrigger={vi.fn()}
      />,
    );
    expect(screen.getByText("暂无正在执行的后台分析任务")).toBeVisible();
    expect(screen.getByText("近期记录中没有失败或警告")).toBeVisible();
  });
});
