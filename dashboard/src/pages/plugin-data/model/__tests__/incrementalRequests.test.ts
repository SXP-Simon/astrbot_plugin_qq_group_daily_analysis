import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { usePluginDataViewModel } from "../usePluginDataViewModel";
import {
  fetchIncrementalBatches,
  fetchIncrementalGroups,
  deleteIncrementalBatch,
  resetIncrementalGroup,
  type IncrementalBatchesResponse,
} from "../../../../entities/plugin-data/api/pluginDataApi";
vi.mock("../../../../entities/plugin-data/api/pluginDataApi");
vi.mock("sonner", () => ({ toast: { success: vi.fn(), error: vi.fn() } }));
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
const response = (group: string): IncrementalBatchesResponse => ({
  total: 1,
  page: 1,
  page_size: 20,
  group_id: group,
  cursor: {
    group_id: group,
    last_analyzed_timestamp: 0,
    last_message_timestamp: 0,
    tracked_message_ids_count: 0,
  },
  batches: [
    {
      group_id: group,
      batch_id: `${group}-batch`,
      timestamp: 1,
      messages_count: 0,
      characters_count: 0,
      topics_count: 0,
    },
  ],
});
function pending<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

it("群聊列表初次选中后自动读取批次，切换时旧响应不能串群", async () => {
  const old = pending<IncrementalBatchesResponse>();
  vi.mocked(fetchIncrementalGroups).mockResolvedValue(["a", "b"]);
  vi.mocked(fetchIncrementalBatches)
    .mockReturnValueOnce(old.promise)
    .mockResolvedValueOnce(response("b"));
  const { result } = renderHook(usePluginDataViewModel);
  await act(async () => result.current.refreshIncrGroups());
  expect(fetchIncrementalBatches).toHaveBeenCalledWith("a", 1, 20);
  await act(async () => result.current.handleSelectIncrGroup("b"));
  expect(result.current.incrBatches).toEqual(response("b").batches);
  await act(async () => old.resolve(response("a")));
  expect(result.current.incrCursor?.group_id).toBe("b");
  expect(result.current.loadingIncremental).toBe(false);
});

it("同群刷新失败保留数据，错配响应被拒绝，切群先清除旧群内容", async () => {
  vi.mocked(fetchIncrementalBatches)
    .mockResolvedValueOnce(response("a"))
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce(response("wrong"));
  const { result } = renderHook(usePluginDataViewModel);
  await act(async () => result.current.handleSelectIncrGroup("a"));
  await act(async () => result.current.loadIncrementalData("a"));
  expect(result.current.incrBatches).toHaveLength(1);
  expect(result.current.incrementalError).toContain("读取失败");
  await act(async () => result.current.handleSelectIncrGroup("b"));
  expect(result.current.incrBatches).toEqual([]);
  expect(result.current.incrCursor).toBeNull();
  expect(result.current.incrementalError).toContain("读取失败");
});

it("删除锁防止重复请求，期间切群后不回写或重查旧群", async () => {
  vi.mocked(fetchIncrementalBatches).mockImplementation(async (group) => response(group));
  const deleting = pending<boolean>();
  vi.mocked(deleteIncrementalBatch).mockReturnValueOnce(deleting.promise);
  const { result } = renderHook(usePluginDataViewModel);
  await act(async () => result.current.handleSelectIncrGroup("a"));
  let first!: Promise<boolean>;
  act(() => {
    first = result.current.handleDeleteBatch("a", "a-batch");
    void result.current.handleDeleteBatch("a", "a-batch");
  });
  expect(deleteIncrementalBatch).toHaveBeenCalledTimes(1);
  await act(async () => result.current.handleSelectIncrGroup("b"));
  await act(async () => {
    deleting.resolve(true);
    await first;
  });
  expect(fetchIncrementalBatches).toHaveBeenCalledTimes(2);
  expect(result.current.incrCursor?.group_id).toBe("b");
  expect(result.current.incrementalBusy).toBe(false);
});

it("删除拒绝与重置错误保留可读原因并允许再次尝试", async () => {
  vi.mocked(deleteIncrementalBatch).mockResolvedValue(false);
  vi.mocked(resetIncrementalGroup)
    .mockRejectedValueOnce(new Error("该群有任务正在运行"))
    .mockResolvedValueOnce({ deleted_batches: 3, message: "ok" });
  vi.mocked(fetchIncrementalGroups).mockResolvedValue([]);
  const { result } = renderHook(usePluginDataViewModel);
  await act(async () => {
    expect(await result.current.handleDeleteBatch("a", "a-batch")).toBe(false);
  });
  expect(result.current.incrementalMutationError).toContain("不存在");
  await act(async () => {
    expect(await result.current.handleResetIncrGroup("a")).toBe(false);
  });
  expect(result.current.incrementalMutationError).toContain("正在运行");
  await act(async () => {
    expect(await result.current.handleResetIncrGroup("a")).toBe(true);
  });
  expect(result.current.incrementalMutationError).toBe("");
});

it("重置后的列表刷新期间卸载，不再发起群聊查询", async () => {
  const reloading = pending<IncrementalBatchesResponse>();
  vi.mocked(fetchIncrementalBatches)
    .mockResolvedValueOnce(response("a"))
    .mockReturnValueOnce(reloading.promise);
  vi.mocked(resetIncrementalGroup).mockResolvedValue({ deleted_batches: 1, message: "ok" });
  const { result, unmount } = renderHook(usePluginDataViewModel);
  await act(async () => result.current.handleSelectIncrGroup("a"));
  let request!: Promise<boolean>;
  await act(async () => {
    request = result.current.handleResetIncrGroup("a");
  });
  unmount();
  await act(async () => {
    reloading.resolve(response("a"));
    await request;
  });
  expect(fetchIncrementalGroups).not.toHaveBeenCalled();
});

it("分页采用服务端总数与修正页码，旧页响应不能覆盖新页", async () => {
  vi.mocked(fetchIncrementalBatches).mockResolvedValueOnce({ ...response("a"), total: 45 });
  const { result } = renderHook(usePluginDataViewModel);
  await act(async () => result.current.handleSelectIncrGroup("a"));
  const second = pending<IncrementalBatchesResponse>();
  vi.mocked(fetchIncrementalBatches)
    .mockReturnValueOnce(second.promise)
    .mockResolvedValueOnce({ ...response("a"), page: 2, total: 40 });
  act(() => {
    void result.current.changeIncrementalPage(2, 20);
  });
  await act(async () => result.current.changeIncrementalPage(3, 20));
  expect(fetchIncrementalBatches).toHaveBeenLastCalledWith("a", 3, 20);
  expect(result.current.incrPagination).toEqual({ page: 2, pageSize: 20, total: 40 });
  await act(async () => second.resolve({ ...response("a"), page: 2, total: 45 }));
  expect(result.current.incrPagination.total).toBe(40);
  vi.mocked(fetchIncrementalBatches).mockResolvedValueOnce({
    ...response("a"),
    page: 2,
    total: 40,
  });
  await act(async () => result.current.loadIncrementalData("a"));
  expect(fetchIncrementalBatches).toHaveBeenLastCalledWith("a", 2, 20);
});
