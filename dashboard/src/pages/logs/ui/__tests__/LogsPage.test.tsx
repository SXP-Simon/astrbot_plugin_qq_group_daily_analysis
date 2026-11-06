import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { LogsPage } from "../LogsPage";
import { useLogsViewModel } from "../../model/useLogsViewModel";
import { fetchPluginLogs, clearPluginLogs } from "../../../../entities/log/api/logApi";
import { copyToClipboard } from "../../../../shared/lib/clipboard";

vi.mock("../../../../entities/log/api/logApi", () => ({
  fetchPluginLogs: vi.fn(),
  clearPluginLogs: vi.fn(),
}));
vi.mock("../../../../shared/api/bridge", () => ({ subscribeSSE: vi.fn() }));
vi.mock("../../../../shared/lib/clipboard", () => ({ copyToClipboard: vi.fn() }));
const onViewTrace = vi.fn();
function Page() {
  return <LogsPage viewModel={useLogsViewModel()} onViewTrace={onViewTrace} />;
}

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchPluginLogs).mockResolvedValue({
    items: [
      {
        id: "example-log",
        timestamp: 100,
        time_str: "12:00:00.000",
        level: "WARNING",
        logger_name: "Render",
        tag: "Render",
        location: "render:20",
        stage: "RENDER_REPORT",
        message: "示例：主服务超时\n备用服务继续渲染",
        raw: "[WARNING] 示例：主服务超时",
        trace_id: "example-trace",
      },
    ],
    total: 1,
    available_tags: [{ key: "Render", label: "报告与长图" }],
  });
  vi.mocked(clearPluginLogs).mockResolvedValue(undefined);
});

it("筛选、暂停、复制与关联任务入口保留；日志区域全选不复制整页", async () => {
  render(<Page />);
  const region = screen.getByRole("region", { name: "日志内容" });
  await waitFor(() => expect(region).toHaveTextContent("备用服务继续渲染"));
  expect(region).toHaveTextContent("WARNING");
  expect(region).toHaveTextContent("render:20");
  fireEvent.click(screen.getByRole("button", { name: "查看任务 example-trace" }));
  expect(onViewTrace).toHaveBeenCalledWith("example-trace");
  fireEvent.click(screen.getByRole("button", { name: "暂停更新" }));
  expect(screen.getByRole("button", { name: "继续更新" })).toHaveAttribute("aria-pressed", "false");
  fireEvent.change(screen.getByRole("searchbox", { name: "搜索日志" }), {
    target: { value: "超时" },
  });
  fireEvent.change(screen.getByLabelText("日志级别"), { target: { value: "CRITICAL" } });
  fireEvent.change(screen.getByLabelText("功能分类"), { target: { value: "Render" } });
  await waitFor(() =>
    expect(fetchPluginLogs).toHaveBeenLastCalledWith(
      expect.objectContaining({ search: "超时", level: "CRITICAL", tag: "Render" }),
    ),
  );
  fireEvent.keyDown(region, { key: "a", ctrlKey: true });
  expect(window.getSelection()?.toString()).toContain("备用服务继续渲染");
  expect(window.getSelection()?.toString()).not.toContain("清空日志");
  vi.mocked(copyToClipboard).mockResolvedValue(false);
  fireEvent.click(screen.getByRole("button", { name: "复制日志" }));
  await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("复制失败"));
});

it("清空先确认，默认焦点在取消；失败保留弹窗和记录，成功后返回按钮", async () => {
  render(<Page />);
  await screen.findByText("示例：主服务超时 备用服务继续渲染");
  const trigger = screen.getByRole("button", { name: "清空日志" });
  trigger.focus();
  fireEvent.click(trigger);
  const dialog = screen.getByRole("dialog", { name: "清空日志缓冲？" });
  expect(dialog).toHaveTextContent("包括被筛选隐藏的记录");
  await waitFor(() => expect(within(dialog).getByRole("button", { name: "取消" })).toHaveFocus());
  expect(clearPluginLogs).not.toHaveBeenCalled();
  vi.mocked(clearPluginLogs).mockRejectedValueOnce(new Error("没有权限"));
  fireEvent.click(within(dialog).getByRole("button", { name: "确认清空" }));
  await waitFor(() => expect(within(dialog).getByRole("alert")).toHaveTextContent("没有权限"));
  expect(screen.getByText("示例：主服务超时 备用服务继续渲染")).toBeInTheDocument();
  fireEvent.click(within(dialog).getByRole("button", { name: "确认清空" }));
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  expect(screen.getByRole("status")).toHaveTextContent("日志缓冲已清空");
  expect(screen.getByText("暂无匹配的插件运行日志")).toBeInTheDocument();
  await waitFor(() => expect(trigger).toHaveFocus());
});
