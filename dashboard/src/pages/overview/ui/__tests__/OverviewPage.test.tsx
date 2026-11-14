import { render, screen, fireEvent, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { OverviewPage } from "@/pages/overview/ui/OverviewPage";
import type { useOverviewViewModel } from "@/pages/overview/model/useOverviewViewModel";
import { mockMetricsSummary } from "@/mocks/data/metrics";
import { mockActiveTasks } from "@/mocks/data/tasks";
import { mockTraces } from "@/mocks/data/traces";

vi.mock("@/widgets/trend-charts/OverviewTrendCharts", () => ({
  OverviewTrendCharts: () => <div>趋势图区域</div>,
}));
function viewModel(): ReturnType<typeof useOverviewViewModel> {
  return {
    metrics: mockMetricsSummary,
    activeTasks: mockActiveTasks.slice(0, 2),
    recentTraces: [],
    attentionTraces: [],
    acknowledgedCount: 0,
    showAcknowledged: false,
    setShowAcknowledged: vi.fn(),
    acknowledgingIds: [],
    acknowledgementError: "",
    handleAcknowledge: vi.fn().mockResolvedValue(undefined),
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
  it("真实统计区保留数量、成功率、耗时和模型消耗的值及单位", () => {
    const vm = viewModel();
    vm.metrics = {
      ...mockMetricsSummary,
      today_traces: 18,
      today_active_groups: 6,
      total_traces: 142,
      success_rate: 95.1,
      avg_duration_ms: 12450,
      today_tokens_spent: 42300,
      total_tokens_spent: 333700,
    };
    render(
      <OverviewPage
        onOpenConfig={vi.fn()}
        viewModel={vm}
        onViewTrace={vi.fn()}
        onOpenTrigger={vi.fn()}
      />,
    );
    const statistics = within(screen.getByRole("region", { name: "分析统计" }));
    const values = statistics.getAllByRole("definition").map((node) => node.textContent);
    expect(values).toEqual(["18次", "6个", "142次", "95.1%", "42,300Tokens", "333,700Tokens"]);
    const tokens = within(statistics.getByRole("group", { name: "模型消耗" }));
    expect(tokens.getAllByRole("term").map((node) => node.textContent)).toEqual([
      "今日模型消耗",
      "近30天模型消耗",
    ]);
    expect(tokens.getAllByRole("definition").map((node) => node.textContent)).toEqual([
      "42,300Tokens",
      "333,700Tokens",
    ]);
  });

  it("统计置顶，任务与提醒在趋势后展示；诊断、中止和发起入口保持可用", async () => {
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
    render(
      <OverviewPage
        onOpenConfig={vi.fn()}
        viewModel={vm}
        onViewTrace={onViewTrace}
        onOpenTrigger={onOpenTrigger}
      />,
    );
    const headings = screen.getAllByRole("heading", { level: 2 }).map((node) => node.textContent);
    expect(headings).toEqual([
      "分析统计",
      "分析运行状态",
      "正在执行中的分析任务 2 运行中",
      "需要关注",
    ]);
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
      <OverviewPage
        onOpenConfig={vi.fn()}
        viewModel={vm}
        onViewTrace={vi.fn()}
        onOpenTrigger={vi.fn()}
      />,
    );
    expect(screen.getAllByText("未读取")).toHaveLength(7);
    expect(screen.queryByText("暂无正在执行的后台分析任务")).not.toBeInTheDocument();
    expect(screen.queryByText("近期记录中没有失败或警告")).not.toBeInTheDocument();
    expect(screen.getAllByRole("alert")).toHaveLength(3);
    fireEvent.click(screen.getByRole("button", { name: "重新加载" }));
    expect(vm.refresh).toHaveBeenCalledWith(false);
    rerender(
      <OverviewPage
        onOpenConfig={vi.fn()}
        viewModel={{ ...vm, tasksLoaded: true, errors: { tasks: "", metrics: "", recent: "" } }}
        onViewTrace={vi.fn()}
        onOpenTrigger={vi.fn()}
      />,
    );
    expect(screen.getByText("暂无正在执行的后台分析任务")).toBeVisible();
    expect(screen.getByText("近期记录中没有失败或警告")).toBeVisible();
  });
});

it("知晓控件语义明确，可显示已知晓和撤销，保存中不能重复点击", () => {
  const vm = viewModel();
  const trace = { ...mockTraces.find((item) => item.status === "failed")!, acknowledged_at: null };
  vm.attentionTraces = [trace];
  const { rerender } = render(
    <OverviewPage
      onOpenConfig={vi.fn()}
      viewModel={vm}
      onViewTrace={vi.fn()}
      onOpenTrigger={vi.fn()}
    />,
  );
  const checkbox = screen.getByRole("checkbox", { name: /已知晓/ });
  fireEvent.click(checkbox);
  expect(vm.handleAcknowledge).toHaveBeenCalledWith(trace.trace_id, true);
  vm.acknowledgingIds = [trace.trace_id];
  rerender(
    <OverviewPage
      onOpenConfig={vi.fn()}
      viewModel={vm}
      onViewTrace={vi.fn()}
      onOpenTrigger={vi.fn()}
    />,
  );
  expect(checkbox).toBeDisabled();
  vm.acknowledgingIds = [];
  vm.attentionTraces = [];
  vm.acknowledgedCount = 1;
  rerender(
    <OverviewPage
      onOpenConfig={vi.fn()}
      viewModel={vm}
      onViewTrace={vi.fn()}
      onOpenTrigger={vi.fn()}
    />,
  );
  expect(screen.getByText("这些提醒均已知晓")).toBeVisible();
  fireEvent.click(screen.getByRole("button", { name: "显示已知晓（1）" }));
  expect(vm.setShowAcknowledged).toHaveBeenCalledWith(true);
  vm.showAcknowledged = true;
  vm.attentionTraces = [{ ...trace, acknowledged_at: 123 }];
  rerender(
    <OverviewPage
      onOpenConfig={vi.fn()}
      viewModel={vm}
      onViewTrace={vi.fn()}
      onOpenTrigger={vi.fn()}
    />,
  );
  const known = screen.getByRole("checkbox", { name: /已知晓/ });
  expect(known).toBeChecked();
  fireEvent.click(known);
  expect(vm.handleAcknowledge).toHaveBeenLastCalledWith(trace.trace_id, false);
  vm.acknowledgementError = "知晓状态未能保存，请稍后重试。";
  rerender(
    <OverviewPage
      onOpenConfig={vi.fn()}
      viewModel={vm}
      onViewTrace={vi.fn()}
      onOpenTrigger={vi.fn()}
    />,
  );
  expect(screen.getByRole("alert")).toHaveTextContent("未能保存");
});
