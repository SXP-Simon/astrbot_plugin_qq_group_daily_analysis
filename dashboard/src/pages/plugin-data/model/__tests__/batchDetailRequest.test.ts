import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import {
  fetchIncrementalBatchDetail,
  type IncrementalBatchItem,
} from "../../../../entities/plugin-data/api/pluginDataApi";
import { usePluginDataViewModel } from "../usePluginDataViewModel";

vi.mock("../../../../entities/plugin-data/api/pluginDataApi");
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
const first: IncrementalBatchItem = {
  group_id: "a",
  batch_id: "one",
  timestamp: 1,
  messages_count: 2,
  characters_count: 3,
  topics_count: 0,
};
const second = { ...first, group_id: "b", batch_id: "two" };
function pending() {
  let resolve!: (value: IncrementalBatchItem | null) => void;
  const promise = new Promise<IncrementalBatchItem | null>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

it("切换批次后旧详情不能覆盖新选择或提前结束加载", async () => {
  const old = pending(),
    current = pending();
  vi.mocked(fetchIncrementalBatchDetail)
    .mockReturnValueOnce(old.promise)
    .mockReturnValueOnce(current.promise);
  const { result } = renderHook(() => usePluginDataViewModel());
  act(() => {
    void result.current.handleOpenBatchDetail(first);
  });
  act(() => {
    void result.current.handleOpenBatchDetail(second);
  });
  await act(async () => old.resolve(first));
  expect(result.current.selectedBatchDetail).toEqual(second);
  expect(result.current.loadingBatchDetail).toBe(true);
  await act(async () => current.resolve({ ...second, messages_count: 20 }));
  expect(result.current.selectedBatchDetail?.messages_count).toBe(20);
  expect(result.current.loadingBatchDetail).toBe(false);
});

it("关闭详情使请求失效，重新打开不混入上次结果", async () => {
  const old = pending();
  vi.mocked(fetchIncrementalBatchDetail)
    .mockReturnValueOnce(old.promise)
    .mockResolvedValueOnce(second);
  const { result } = renderHook(() => usePluginDataViewModel());
  act(() => {
    void result.current.handleOpenBatchDetail(first);
  });
  act(() => result.current.handleCloseBatchDetail());
  await act(async () => old.resolve(first));
  expect(result.current.selectedBatchDetail).toBeNull();
  expect(result.current.batchDetailModalOpen).toBe(false);
  expect(result.current.loadingBatchDetail).toBe(false);
  await act(async () => result.current.handleOpenBatchDetail(second));
  expect(result.current.selectedBatchDetail).toEqual(second);
});

it("读取失败可重试；空记录和错配记录不会当作完整数据", async () => {
  vi.mocked(fetchIncrementalBatchDetail)
    .mockRejectedValueOnce(new Error("offline"))
    .mockResolvedValueOnce(null)
    .mockResolvedValueOnce(second)
    .mockResolvedValueOnce(first);
  const { result } = renderHook(() => usePluginDataViewModel());
  for (const message of ["读取失败", "不存在", "不一致"]) {
    await act(async () => result.current.handleOpenBatchDetail(first));
    expect(result.current.batchDetailError).toContain(message);
    expect(result.current.selectedBatchDetail?.batch_id).toBe(first.batch_id);
  }
  await act(async () => result.current.handleOpenBatchDetail(first));
  expect(result.current.batchDetailError).toBe("");
});

it("卸载后迟到结果不继续更新或提示错误", async () => {
  const old = pending();
  vi.mocked(fetchIncrementalBatchDetail).mockReturnValueOnce(old.promise);
  const { result, unmount } = renderHook(() => usePluginDataViewModel());
  act(() => {
    void result.current.handleOpenBatchDetail(first);
  });
  unmount();
  await act(async () => old.resolve(second));
  expect(result.current.selectedBatchDetail).toEqual(first);
  expect(result.current.batchDetailError).toBe("");
});
