import { afterEach, expect, it, vi } from "vitest";
import {
  act,
  cleanup,
  fireEvent,
  render,
  renderHook,
  screen,
  within,
} from "@testing-library/react";
import { IncrementalTab } from "@/pages/plugin-data/ui/incremental/IncrementalTab";
import { usePluginDataViewModel } from "@/pages/plugin-data/model/usePluginDataViewModel";
import type { RecordLocator } from "@/entities/plugin-data/api/managedRecordsApi";

vi.mock("@/pages/plugin-data/ui/ManagedRecordDialog", () => ({
  ManagedRecordDialog: ({ locator }: { locator: RecordLocator | null }) =>
    locator ? (
      <output aria-label="管理目标">
        {locator.group_id}/{locator.batch_id}
      </output>
    ) : null,
}));

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

it("操作按钮指向所在批次，删除仍需确认且可取消", async () => {
  const computedStyle = window.getComputedStyle.bind(window);
  vi.spyOn(window, "getComputedStyle").mockImplementation((element) => computedStyle(element));
  const { result } = renderHook(() => usePluginDataViewModel());
  const batches = ["batch-a", "batch-b"].map((batch_id) => ({
    batch_id,
    group_id: "group-a",
    timestamp: 1794000000,
    messages_count: 10,
    characters_count: 50,
    topics_count: 0,
  }));
  const openDetail = vi.fn();
  const deleteBatch = vi.fn().mockResolvedValue(true);
  render(
    <IncrementalTab
      vm={{
        ...result.current,
        selectedIncrGroup: "group-a",
        incrGroups: ["group-a"],
        incrBatches: batches,
        handleOpenBatchDetail: openDetail,
        handleDeleteBatch: deleteBatch,
      }}
    />,
  );
  const row = screen.getByText("batch-b").closest("tr")!;
  fireEvent.click(within(row).getByRole("button", { name: "详情" }));
  expect(openDetail).toHaveBeenCalledWith(batches[1]);
  fireEvent.click(within(row).getByRole("button", { name: "管理" }));
  expect(screen.getByLabelText("管理目标")).toHaveTextContent("group-a/batch-b");
  fireEvent.click(within(row).getByRole("button", { name: "删除" }));
  expect(deleteBatch).not.toHaveBeenCalled();
  let confirmation = await screen.findByRole("dialog");
  expect(confirmation).toHaveTextContent("删除后该批次的话题与统计数据将不再参与汇总计算。");
  fireEvent.click(within(confirmation).getByRole("button", { name: /取\s*消/ }));
  expect(deleteBatch).not.toHaveBeenCalled();
  fireEvent.click(within(row).getByRole("button", { name: "删除" }));
  confirmation = await screen.findByRole("dialog");
  await act(async () => {
    fireEvent.click(within(confirmation).getByRole("button", { name: /删\s*除/ }));
  });
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  expect(deleteBatch).toHaveBeenCalledTimes(1);
  expect(deleteBatch).toHaveBeenCalledWith("group-a", "batch-b", "");
});

it("删除失败时确认框保持打开，重新处理仍绑定原批次", async () => {
  const { result } = renderHook(usePluginDataViewModel);
  const batch = {
    batch_id: "keep-me",
    group_id: "a",
    timestamp: 1,
    messages_count: 0,
    characters_count: 0,
    topics_count: 0,
    token_usage: { total_tokens: 0 },
  };
  const remove = vi.fn().mockResolvedValue(false);
  const vm = {
    ...result.current,
    selectedIncrGroup: "a",
    incrGroups: ["a"],
    incrBatches: [batch],
    handleDeleteBatch: remove,
  };
  const { rerender } = render(<IncrementalTab vm={vm} />);
  expect(screen.getByRole("region", { name: "增量批次列表" })).toHaveTextContent("0");
  fireEvent.click(screen.getByRole("button", { name: "删除" }));
  const dialog = screen.getByRole("dialog");
  await act(async () => fireEvent.click(within(dialog).getByRole("button", { name: "删除" })));
  rerender(<IncrementalTab vm={{ ...vm, incrementalMutationError: "当前群有任务正在运行" }} />);
  expect(screen.getByRole("dialog")).toHaveTextContent("keep-me");
  expect(screen.getByRole("alert")).toHaveTextContent("当前群有任务正在运行");
  expect(remove).toHaveBeenCalledWith("a", "keep-me", "");
});

it("超过选择上限时全选最多 200 条，并可再次点击取消", () => {
  const { result } = renderHook(usePluginDataViewModel);
  const batches = Array.from({ length: 201 }, (_, index) => ({
    batch_id: `batch-${index}`,
    group_id: "a",
    timestamp: 1,
    messages_count: 0,
    characters_count: 0,
    topics_count: 0,
  }));
  render(
    <IncrementalTab
      vm={{ ...result.current, selectedIncrGroup: "a", incrGroups: ["a"], incrBatches: batches }}
    />,
  );
  const selectAll = screen.getByRole("checkbox", { name: "选择本页批次（最多 200）" });
  fireEvent.click(selectAll);
  expect(selectAll).toBeChecked();
  expect(screen.getAllByRole("checkbox", { checked: true })).toHaveLength(201);
  fireEvent.click(selectAll);
  expect(screen.queryAllByRole("checkbox", { checked: true })).toHaveLength(0);
});

it("分页选择保留其他页，取消本页全选不会清空其他页", () => {
  const { result } = renderHook(usePluginDataViewModel);
  const batch = (id: string) => ({
    group_id: "a",
    batch_id: id,
    timestamp: 1,
    messages_count: 1,
    characters_count: 2,
  });
  const vm = {
    ...result.current,
    selectedIncrGroup: "a",
    incrGroups: ["a"],
    incrPagination: { page: 1, pageSize: 20, total: 21 },
  };
  const { rerender } = render(<IncrementalTab vm={{ ...vm, incrBatches: [batch("first")] }} />);
  fireEvent.click(screen.getByLabelText("选择批次 first"));
  rerender(
    <IncrementalTab
      vm={{
        ...vm,
        incrPagination: { ...vm.incrPagination, page: 2 },
        incrBatches: [batch("last")],
      }}
    />,
  );
  fireEvent.click(screen.getByLabelText("选择本页批次（最多 200）"));
  expect(screen.getByText(/已选 2 项/)).toBeVisible();
  fireEvent.click(screen.getByLabelText("选择本页批次（最多 200）"));
  expect(screen.getByText(/已选 1 项/)).toBeVisible();
  rerender(<IncrementalTab vm={{ ...vm, incrBatches: [batch("first")] }} />);
  expect(screen.getByLabelText("选择批次 first")).toBeChecked();
  expect(screen.getByLabelText("选择批次 first").closest("tr")).toHaveAttribute(
    "aria-selected",
    "true",
  );
});

it("增量群聊可按群名或群号搜索，同号群选择携带平台身份", () => {
  const { result } = renderHook(usePluginDataViewModel);
  const select = vi.fn();
  render(
    <IncrementalTab
      vm={{
        ...result.current,
        incrGroups: ["123"],
        selectedIncrGroup: "123",
        selectedIncrPlatform: "onebot",
        selectedIncrSessionKey: '["onebot","123"]',
        incrGroupOptions: [
          { value: '["onebot","123"]', label: "技术群（123） · onebot" },
          { value: '["telegram","123"]', label: "摄影群（123） · telegram" },
        ],
        handleSelectIncrSession: select,
      }}
    />,
  );
  expect(screen.queryByText(/这个群号关联多个平台/)).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /选择增量群聊：技术群/ }));
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "摄影" } });
  fireEvent.click(screen.getByRole("button", { name: "摄影群（123） · telegram" }));
  expect(select).toHaveBeenCalledWith('["telegram","123"]');
});
