import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { ContextInsightPage } from "../ContextInsightPage";
import { useContextInsightViewModel } from "../../model/useContextInsightViewModel";
import { fetchTraceList, fetchTraceDetail } from "../../../../entities/trace/api/traceApi";
import { fetchGroupSessions } from "../../../../entities/group/api/groupApi";
import type { TraceRecord } from "../../../../entities/trace/model/types";

vi.mock("../../../../entities/trace/api/traceApi", () => ({
  fetchTraceList: vi.fn(),
  fetchTraceDetail: vi.fn(),
}));
vi.mock("../../../../entities/group/api/groupApi", () => ({ fetchGroupSessions: vi.fn() }));
vi.mock("../../../../widgets/timeline-picker/AnalysisTimelinePicker", () => ({
  AnalysisTimelinePicker: () => null,
}));
vi.mock("echarts-for-react", () => ({ default: () => null }));
vi.mock("../../../../shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));

const traces: TraceRecord[] = ["a", "b"].map((id) => ({
  trace_id: `example-${id}`,
  group_name: `示例群聊 ${id}`,
  group_id: "123",
  platform: id === "a" ? "telegram" : "discord",
  trigger_type: "manual",
  status: "succeeded",
  started_at: 100,
  total_tokens: id === "a" ? 100 : 0,
}));
const onViewTrace = vi.fn();
function Page() {
  return <ContextInsightPage viewModel={useContextInsightViewModel()} onViewTrace={onViewTrace} />;
}

beforeEach(() => {
  vi.mocked(fetchTraceList).mockResolvedValue({ items: traces, total: 300 });
  vi.mocked(fetchTraceDetail).mockImplementation(
    async (id) => traces.find((trace) => trace.trace_id === id) ?? null,
  );
  vi.mocked(fetchGroupSessions).mockResolvedValue([]);
});
afterEach(() => vi.resetAllMocks());

it("通过可搜索选择器切换同群号不同平台的任务，详情入口与数据一致，日期清空后同步表单", async () => {
  render(<Page />);
  await screen.findByRole("button", { name: "查看任务详情" });
  expect(screen.getByText("已载入 2 条 · 首次查询共 300 条")).toBeVisible();
  const selection = screen.getByRole("button", { name: /选择分析记录：/ });
  selection.focus();
  fireEvent.click(selection);
  const dialog = screen.getByRole("dialog");
  fireEvent.change(within(dialog).getByRole("searchbox"), { target: { value: "discord" } });
  const option = within(dialog).getByRole("button", { name: /示例群聊 b/ });
  option.focus();
  fireEvent.click(option);
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  await waitFor(() => expect(selection).toHaveFocus());
  const stats = screen.getByRole("region", { name: "所选任务统计" });
  expect(within(stats).getByRole("heading", { name: "示例群聊 b" })).toBeVisible();
  expect(within(stats).getByText("总 Tokens").parentElement).toHaveTextContent("0");
  expect(within(stats).getByText("输入 Tokens").parentElement).toHaveTextContent("未记录");
  fireEvent.click(within(stats).getByRole("button", { name: "查看任务详情" }));
  expect(onViewTrace).toHaveBeenCalledWith("example-b");
  fireEvent.change(screen.getByLabelText("开始日期"), { target: { value: "2026-10-01" } });
  fireEvent.change(screen.getByLabelText("结束日期"), { target: { value: "2026-10-02" } });
  await waitFor(() =>
    expect(fetchTraceList).toHaveBeenLastCalledWith(
      expect.objectContaining({ start_time: expect.any(Number), end_time: expect.any(Number) }),
    ),
  );
  fireEvent.click(screen.getByRole("button", { name: "清空筛选" }));
  expect(screen.getByLabelText("开始日期")).toHaveValue("");
  expect(screen.getByLabelText("结束日期")).toHaveValue("");
});

it("失败与空数据分开显示，刷新可以恢复，不用零图表掩盖未加载", async () => {
  vi.mocked(fetchTraceList).mockRejectedValueOnce(new Error("宿主连接失败"));
  render(<Page />);
  expect(await screen.findByRole("alert")).toHaveTextContent("宿主连接失败");
  expect(screen.queryByText(/暂无符合条件/)).not.toBeInTheDocument();
  expect(screen.queryByRole("region", { name: "消息留存" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "刷新" }));
  await screen.findByRole("button", { name: "查看任务详情" });
  vi.mocked(fetchTraceList).mockRejectedValueOnce(new Error("刷新失败"));
  fireEvent.click(screen.getByRole("button", { name: "刷新" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("当前保留上次读取的记录");
  vi.mocked(fetchTraceList).mockResolvedValueOnce({ items: [], total: 0 });
  fireEvent.click(screen.getByRole("button", { name: "刷新" }));
  expect(await screen.findByText(/所选任务已不在当前加载范围/)).toBeVisible();
  expect(screen.queryByRole("region", { name: "所选任务统计" })).not.toBeInTheDocument();
});

it("加载期间记录增加时区分已载入数量和首次查询总数", async () => {
  vi.mocked(fetchTraceList)
    .mockResolvedValueOnce({ items: [traces[0]], total: 1, has_more: true })
    .mockResolvedValueOnce({ items: [traces[1]], total: 1, has_more: false });
  render(<Page />);
  fireEvent.click(await screen.findByRole("button", { name: "加载更早记录" }));
  expect(await screen.findByText("已载入 2 条 · 首次查询共 1 条")).toBeVisible();
});
