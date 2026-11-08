import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { fetchTraceList } from "../../../../entities/trace/api/traceApi";
import { fetchGroupSessions } from "../../../../entities/group/api/groupApi";
import type { TraceRecord } from "../../../../entities/trace/model/types";
import { useTracesViewModel } from "../useTracesViewModel";

vi.mock("../../../../entities/trace/api/traceApi", () => ({ fetchTraceList: vi.fn() }));
vi.mock("../../../../entities/group/api/groupApi", () => ({ fetchGroupSessions: vi.fn() }));

const trace: TraceRecord = {
  trace_id: "example-a",
  group_id: "group-a",
  group_name: "示例群聊",
  platform: "telegram",
  trigger_type: "manual",
  status: "succeeded",
  started_at: 100,
};

beforeEach(() => {
  vi.useFakeTimers();
  vi.mocked(fetchTraceList).mockResolvedValue({ items: [trace], total: 31 });
  vi.mocked(fetchGroupSessions).mockResolvedValue([]);
});
afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
});

it("筛选修改立即废弃旧响应，连续搜索只请求最后输入", async () => {
  let resolve!: (value: Awaited<ReturnType<typeof fetchTraceList>>) => void;
  vi.mocked(fetchTraceList).mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    }),
  );
  const { result } = renderHook(useTracesViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  act(() => result.current.setSearch("摄"));
  await act(async () => resolve({ items: [trace], total: 31 }));
  expect(result.current.traces).toEqual([]);
  expect(result.current.loading).toBe(true);
  await act(async () => vi.advanceTimersByTimeAsync(100));
  act(() => result.current.setSearch(" 摄影 "));
  await act(async () => vi.advanceTimersByTimeAsync(249));
  expect(fetchTraceList).toHaveBeenCalledTimes(1);
  await act(async () => vi.advanceTimersByTimeAsync(1));
  expect(fetchTraceList).toHaveBeenCalledTimes(2);
  expect(fetchTraceList).toHaveBeenLastCalledWith(
    expect.objectContaining({ search: "摄影", offset: 0 }),
  );
  expect(result.current.traces).toEqual([trace]);
});

it("切换排序、筛选和条数使用一致的第一页查询，刷新保留当前条件", async () => {
  const { result } = renderHook(useTracesViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  act(() => result.current.changePage(3, 15));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(fetchTraceList).toHaveBeenLastCalledWith(
    expect.objectContaining({ offset: 30, limit: 15 }),
  );
  act(() => result.current.changeSort("duration_ms"));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(fetchTraceList).toHaveBeenLastCalledWith(
    expect.objectContaining({ offset: 0, sort_by: "duration_ms", sort_order: "desc" }),
  );
  act(() => result.current.changeSort("duration_ms"));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.sortOrder).toBe("asc");
  act(() => {
    result.current.setSelectedGroup("group-a");
    result.current.setStatusFilter("failed");
    result.current.setTriggerTypeFilter("web_manual");
    result.current.setDateRange([100, 200]);
    result.current.changePage(1, 50);
  });
  await act(async () => vi.advanceTimersByTimeAsync(0));
  const query = {
    offset: 0,
    limit: 50,
    group_id: "group-a",
    status: "failed",
    trigger_type: "web_manual",
    start_time: 100,
    end_time: 200,
    sort_by: "duration_ms",
    sort_order: "asc",
    search: undefined,
  };
  expect(fetchTraceList).toHaveBeenLastCalledWith(query);
  act(() => result.current.refresh());
  expect(result.current.loading).toBe(false);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(fetchTraceList).toHaveBeenLastCalledWith(query);
  act(() => result.current.resetFilters());
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(fetchTraceList).toHaveBeenLastCalledWith(
    expect.objectContaining({
      limit: 50,
      offset: 0,
      group_id: undefined,
      status: undefined,
      start_time: undefined,
      trigger_type: undefined,
      sort_order: "asc",
    }),
  );
});

it("加载失败保留输入与已有结果，手动刷新可恢复", async () => {
  const { result } = renderHook(useTracesViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  vi.mocked(fetchTraceList).mockRejectedValueOnce(new Error("宿主暂未响应"));
  vi.mocked(fetchGroupSessions).mockRejectedValueOnce(new Error("群聊不可用"));
  act(() => {
    result.current.setSearch("摄影");
    result.current.refresh(false);
  });
  await act(async () => vi.advanceTimersByTimeAsync(250));
  expect(result.current.search).toBe("摄影");
  expect(result.current.traces).toEqual([trace]);
  expect(result.current.error).toContain("宿主暂未响应");
  expect(result.current.groupsError).toContain("群聊不可用");
  expect(result.current.loading).toBe(false);
  act(() => result.current.refresh(false));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.error).toBe("");
  expect(result.current.groupsError).toBe("");
});

it("记录减少使当前页越界时，重新请求最后一页而非留下空白", async () => {
  const { result } = renderHook(useTracesViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  vi.mocked(fetchTraceList).mockResolvedValue({ items: [trace], total: 16 });
  act(() => result.current.changePage(3, 15));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  await act(async () => vi.advanceTimersByTimeAsync(1));
  expect(result.current.page).toBe(2);
  expect(result.current.total).toBe(16);
  expect(fetchTraceList).toHaveBeenLastCalledWith(expect.objectContaining({ offset: 15 }));
});

it("卸载清理搜索定时器，迟到的请求不再产生后续查询", async () => {
  let resolve!: (value: Awaited<ReturnType<typeof fetchTraceList>>) => void;
  vi.mocked(fetchTraceList).mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    }),
  );
  const view = renderHook(useTracesViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  act(() => view.result.current.setSearch("摄影"));
  view.unmount();
  await act(async () => {
    resolve({ items: [trace], total: 31 });
    await vi.advanceTimersByTimeAsync(1000);
  });
  expect(fetchTraceList).toHaveBeenCalledTimes(1);
  expect(vi.getTimerCount()).toBe(0);
});
it("更新通知不重排或重查当前历史页，主动刷新才更新结果", async () => {
  const { result } = renderHook(useTracesViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  const calls = vi.mocked(fetchTraceList).mock.calls.length;
  const before = result.current.traces;
  act(() => result.current.markUpdated());
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.hasUpdates).toBe(true);
  expect(result.current.traces).toBe(before);
  expect(fetchTraceList).toHaveBeenCalledTimes(calls);
  act(() => result.current.refresh(false));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(fetchTraceList).toHaveBeenCalledTimes(calls + 1);
  expect(result.current.hasUpdates).toBe(false);
});

it("平台变更清空群聊，群聊选择携带平台身份", async () => {
  const { result } = renderHook(useTracesViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  act(() => result.current.setSelectedGroup("same", "telegram"));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(fetchTraceList).toHaveBeenLastCalledWith(
    expect.objectContaining({ group_id: "same", platform: "telegram" }),
  );
  act(() => result.current.setSelectedPlatform(""));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(fetchTraceList).toHaveBeenLastCalledWith(
    expect.objectContaining({ group_id: undefined, platform: "" }),
  );
});

it("连续切页立即更新目标，旧页成功或失败都不能覆盖最终选择", async () => {
  vi.mocked(fetchTraceList).mockResolvedValueOnce({ items: [trace], total: 60 });
  const { result } = renderHook(useTracesViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  let resolve!: (value: Awaited<ReturnType<typeof fetchTraceList>>) => void;
  let reject!: (error: Error) => void;
  vi.mocked(fetchTraceList)
    .mockReturnValueOnce(
      new Promise((done, fail) => {
        resolve = done;
        reject = fail;
      }),
    )
    .mockResolvedValueOnce({ items: [{ ...trace, trace_id: "example-page-3" }], total: 60 });
  act(() => result.current.changePage(2, 15));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.page).toBe(2);
  expect(result.current.total).toBe(60);
  expect(result.current.loading).toBe(true);
  act(() => result.current.changePage(3, 15));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  await act(async () => resolve({ items: [trace], total: 1 }));
  expect(result.current.page).toBe(3);
  expect(result.current.traces[0].trace_id).toBe("example-page-3");
  expect(result.current.total).toBe(60);
  expect(result.current.loading).toBe(false);

  vi.mocked(fetchTraceList)
    .mockReturnValueOnce(
      new Promise((_, fail) => {
        reject = fail;
      }),
    )
    .mockResolvedValueOnce({ items: [trace], total: 60 });
  act(() => result.current.changePage(2, 15));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  act(() => result.current.changePage(1, 15));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  await act(async () => reject(new Error("迟到的失败")));
  expect(result.current.page).toBe(1);
  expect(result.current.error).toBe("");
  expect(result.current.loading).toBe(false);
});
