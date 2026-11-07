import {
  act,
  cleanup,
  fireEvent,
  render,
  renderHook,
  screen,
  within,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { usePluginDataViewModel } from "../../../model/usePluginDataViewModel";
import { CheckpointsTab } from "../CheckpointsTab";
import type { RecordLocator } from "../../../../../entities/plugin-data/api/managedRecordsApi";
vi.mock("../../ManagedRecordDialog", () => ({
  ManagedRecordDialog: ({ locator }: { locator: RecordLocator | null }) =>
    locator ? <output aria-label="管理目标">{locator.trace_id}</output> : null,
}));
afterEach(cleanup);
const item = {
  group_id: "a",
  date_str: "2026-11-07",
  stage_name: "LLM_ANALYSIS",
  trace_id: "trace-a",
  data_size_bytes: 0,
};
it("筛选清空与页码跳转使用明确参数，删除确认绑定原任务且失败不关闭", async () => {
  const { result } = renderHook(usePluginDataViewModel);
  const load = vi.fn();
  const remove = vi.fn().mockResolvedValue(false);
  const detail = vi.fn();
  const vm = {
    ...result.current,
    checkpoints: [item],
    checkpointsTotal: 62,
    ckptGroups: ["a", "b"],
    ckptFilterGroup: "a",
    loadCheckpoints: load,
    handleDeleteCheckpoint: remove,
    handleOpenCkptDetail: detail,
  };
  const { rerender } = render(<CheckpointsTab vm={vm} />);
  fireEvent.change(screen.getByLabelText("群聊"), { target: { value: "" } });
  expect(load).toHaveBeenLastCalledWith({ page: 1, group: undefined });
  fireEvent.click(screen.getByRole("button", { name: "清空筛选" }));
  expect(load).toHaveBeenLastCalledWith({
    page: 1,
    group: undefined,
    date: undefined,
    stage: undefined,
  });
  fireEvent.change(screen.getByLabelText("跳到页码"), { target: { value: "3" } });
  fireEvent.click(screen.getByRole("button", { name: "跳转" }));
  expect(load).toHaveBeenLastCalledWith({ page: 3 });
  fireEvent.click(screen.getByRole("button", { name: "产物 JSON" }));
  expect(detail).toHaveBeenCalledWith(item);
  fireEvent.click(screen.getByRole("button", { name: "管理" }));
  expect(screen.getByLabelText("管理目标")).toHaveTextContent("trace-a");
  fireEvent.click(screen.getByRole("button", { name: "删除" }));
  expect(remove).not.toHaveBeenCalled();
  rerender(<CheckpointsTab vm={{ ...vm, checkpoints: [{ ...item, trace_id: "trace-new" }] }} />);
  await act(async () =>
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "删除" })),
  );
  expect(remove).toHaveBeenCalledWith("a", "2026-11-07", "LLM_ANALYSIS", "trace-a");
  expect(screen.getByRole("dialog")).toHaveTextContent("trace-a");
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "取消" }));
  expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
});
it("跨页选择保持，换筛选后清除选择", () => {
  const { result } = renderHook(usePluginDataViewModel);
  const vm = {
    ...result.current,
    checkpoints: [item],
    ckptGroups: ["a", "b"],
    ckptFilterGroup: "a",
  };
  const { rerender } = render(<CheckpointsTab vm={vm} />);
  fireEvent.click(screen.getByRole("checkbox", { name: "选择本页快照" }));
  expect(screen.getByText("已选 1 项（最多 200）")).toBeInTheDocument();
  rerender(
    <CheckpointsTab
      vm={{ ...vm, checkpointsPage: 2, checkpoints: [{ ...item, trace_id: "b" }] }}
    />,
  );
  fireEvent.click(screen.getByRole("checkbox", { name: "选择本页快照" }));
  expect(screen.getByText("已选 2 项（最多 200）")).toBeInTheDocument();
  rerender(<CheckpointsTab vm={{ ...vm, ckptFilterGroup: "b" }} />);
  expect(screen.getByText("已选 0 项（最多 200）")).toBeInTheDocument();
});
