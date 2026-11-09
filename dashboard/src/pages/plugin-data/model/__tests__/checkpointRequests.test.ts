import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useCheckpointsViewModel } from "@/pages/plugin-data/model/useCheckpointsViewModel";
import {
  fetchCheckpointGroups,
  fetchCheckpointsList,
  fetchCheckpointDetail,
  deleteCheckpoint,
} from "@/entities/plugin-data/api/pluginDataApi";
import type { CheckpointDetail, CheckpointsListResponse } from "@/entities/plugin-data/model/types";
vi.mock("@/entities/plugin-data/api/pluginDataApi");
vi.mock("sonner", () => ({ toast: { success: vi.fn() } }));
beforeEach(() => {
  vi.mocked(fetchCheckpointGroups).mockResolvedValue([]);
  vi.mocked(fetchCheckpointsList).mockResolvedValue({ items: [], total: 0 });
});
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
});
const item = {
  group_id: "a",
  date_str: "2026-11-07",
  stage_name: "LLM_ANALYSIS",
  trace_id: "task-a",
};
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { resolve, promise };
}
it("清空筛选明确移除旧条件，快速翻页只保留最后一次结果", async () => {
  const old = deferred<CheckpointsListResponse>();
  vi.mocked(fetchCheckpointsList)
    .mockResolvedValueOnce({ items: [item], total: 60 })
    .mockReturnValueOnce(old.promise)
    .mockResolvedValueOnce({ items: [{ ...item, trace_id: "latest" }], total: 60 });
  const { result } = renderHook(useCheckpointsViewModel);
  await act(async () =>
    result.current.loadCheckpoints({ group: "a", date: "2026-11-07", stage: "LLM_ANALYSIS" }),
  );
  let previous!: Promise<void>;
  act(() => {
    previous = result.current.loadCheckpoints({ page: 2 });
  });
  expect(result.current.checkpointsPage).toBe(2);
  expect(result.current.checkpointsTotal).toBe(60);
  expect(result.current.loadingCheckpoints).toBe(true);
  await act(async () =>
    result.current.loadCheckpoints({
      page: 3,
      group: undefined,
      date: undefined,
      stage: undefined,
    }),
  );
  expect(fetchCheckpointsList).toHaveBeenLastCalledWith({
    offset: 40,
    limit: 20,
    group_id: undefined,
    date_str: undefined,
    stage_name: undefined,
  });
  await act(async () => {
    old.resolve({ items: [item], total: 60 });
    await previous;
  });
  expect(result.current.checkpoints[0].trace_id).toBe("latest");
  expect(result.current.checkpointsPage).toBe(3);
});
it("记录减少后重查末页，同条件刷新失败保留已读内容", async () => {
  vi.mocked(fetchCheckpointsList)
    .mockResolvedValueOnce({ items: [], total: 21 })
    .mockResolvedValueOnce({ items: [item], total: 21 })
    .mockRejectedValueOnce(new Error("offline"));
  const { result } = renderHook(useCheckpointsViewModel);
  await act(async () => result.current.loadCheckpoints({ page: 4 }));
  expect(fetchCheckpointsList).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 20 }));
  expect(result.current.checkpointsPage).toBe(2);
  await act(async () => result.current.loadCheckpoints());
  expect(result.current.checkpoints).toEqual([item]);
  expect(result.current.checkpointError).toContain("offline");
});
it("详情切换、关闭和卸载后不接受旧响应", async () => {
  const old = deferred<CheckpointDetail | null>();
  const newer = deferred<CheckpointDetail | null>();
  vi.mocked(fetchCheckpointDetail)
    .mockReturnValueOnce(old.promise)
    .mockReturnValueOnce(newer.promise);
  const { result, unmount } = renderHook(useCheckpointsViewModel);
  let first!: Promise<void>;
  let second!: Promise<void>;
  act(() => {
    first = result.current.handleOpenCkptDetail(item);
    second = result.current.handleOpenCkptDetail({ ...item, trace_id: "b" });
  });
  await act(async () => {
    old.resolve({ ...item, data: { wrong: true } });
    await first;
  });
  expect(result.current.selectedCkptDetail?.trace_id).toBe("b");
  act(() => result.current.handleCloseCkptDetail());
  await act(async () => {
    newer.resolve({ ...item, trace_id: "b", data: {} });
    await second;
  });
  expect(result.current.selectedCkptDetail).toBeNull();
  const pending = deferred<CheckpointDetail | null>();
  vi.mocked(fetchCheckpointDetail).mockReturnValueOnce(pending.promise);
  act(() => {
    first = result.current.handleOpenCkptDetail(item);
  });
  unmount();
  await act(async () => {
    pending.resolve({ ...item, data: {} });
    await first;
  });
});
it("错误任务快照被拒绝，重试可显示空产物且不捏造元数据", async () => {
  vi.mocked(fetchCheckpointDetail)
    .mockResolvedValueOnce({ ...item, trace_id: "wrong", data: {} })
    .mockResolvedValueOnce({ ...item, checkpoint_data: {} });
  const { result } = renderHook(useCheckpointsViewModel);
  await act(async () => result.current.handleOpenCkptDetail(item));
  expect(result.current.checkpointDetailError).toContain("不一致");
  await act(async () => result.current.handleOpenCkptDetail(item));
  expect(result.current.checkpointDetailError).toBe("");
  expect(result.current.selectedCkptDetail?.data).toEqual({});
});
it("删除只提交一次，失败保留原因，切换范围后不刷新旧筛选", async () => {
  const pending = deferred<boolean>();
  vi.mocked(deleteCheckpoint)
    .mockRejectedValueOnce(new Error("群聊任务正在运行"))
    .mockReturnValueOnce(pending.promise);
  const { result } = renderHook(useCheckpointsViewModel);
  await act(async () => {
    expect(
      await result.current.handleDeleteCheckpoint("a", item.date_str, item.stage_name, "task-a"),
    ).toBe(false);
  });
  expect(result.current.checkpointDeleteError).toContain("正在运行");
  let request!: Promise<boolean>;
  act(() => {
    request = result.current.handleDeleteCheckpoint("a", item.date_str, item.stage_name, "task-a");
    void result.current.handleDeleteCheckpoint("a", item.date_str, item.stage_name, "task-a");
  });
  expect(deleteCheckpoint).toHaveBeenCalledTimes(2);
  await act(async () => result.current.loadCheckpoints({ group: "b", page: 1 }));
  await act(async () => {
    pending.resolve(true);
    await request;
  });
  expect(fetchCheckpointsList).toHaveBeenCalledTimes(1);
  expect(result.current.ckptFilterGroup).toBe("b");
});
it("群聊选项读取失败保留旧选项，卸载时使未完成列表失效", async () => {
  vi.mocked(fetchCheckpointGroups)
    .mockResolvedValueOnce([{ group_id: "a", group_name: "示例群", platform: "telegram" }])
    .mockRejectedValueOnce(new Error());
  const { result, unmount } = renderHook(useCheckpointsViewModel);
  await act(async () => result.current.refreshCheckpointGroups());
  await act(async () => result.current.refreshCheckpointGroups());
  expect(result.current.ckptGroups).toEqual([
    { group_id: "a", group_name: "示例群", platform: "telegram" },
  ]);
  expect(result.current.checkpointGroupsError).not.toBe("");
  const pending = deferred<CheckpointsListResponse>();
  vi.mocked(fetchCheckpointsList).mockReturnValueOnce(pending.promise);
  let request!: Promise<void>;
  act(() => {
    request = result.current.loadCheckpoints();
  });
  unmount();
  await act(async () => {
    pending.resolve({ items: [item], total: 1 });
    await request;
  });
});

it("平台筛选在页码修正后继续保留，切换平台立即隔离旧结果", async () => {
  const { result } = renderHook(useCheckpointsViewModel);
  vi.mocked(fetchCheckpointsList).mockResolvedValue({ items: [], total: 1 });
  await act(async () =>
    result.current.loadCheckpoints({ page: 5, group: "123", platform: "telegram" }),
  );
  expect(fetchCheckpointsList).toHaveBeenLastCalledWith(
    expect.objectContaining({ offset: 0, group_id: "123", platform: "telegram" }),
  );
  await act(async () =>
    result.current.loadCheckpoints({ page: 1, group: undefined, platform: "" }),
  );
  expect(result.current.ckptFilterPlatform).toBe("");
  expect(fetchCheckpointsList).toHaveBeenLastCalledWith(
    expect.objectContaining({ group_id: undefined, platform: "" }),
  );
});
