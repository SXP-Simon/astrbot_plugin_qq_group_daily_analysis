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
import { IncrementalTab } from "../IncrementalTab";
import { usePluginDataViewModel } from "../../../model/usePluginDataViewModel";
import type { RecordLocator } from "../../../../../entities/plugin-data/api/managedRecordsApi";

vi.mock("../../ManagedRecordDialog", () => ({
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
  const deleteBatch = vi.fn().mockResolvedValue(undefined);
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
  expect(deleteBatch).toHaveBeenCalledWith("group-a", "batch-b");
});
