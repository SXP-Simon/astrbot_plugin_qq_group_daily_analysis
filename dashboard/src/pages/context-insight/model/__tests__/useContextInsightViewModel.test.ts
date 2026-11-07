import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { fetchTraceList, fetchTraceDetail } from "../../../../entities/trace/api/traceApi";
import { fetchDistinctGroups } from "../../../../entities/group/api/groupApi";
import type { TraceRecord } from "../../../../entities/trace/model/types";
import { useContextInsightViewModel } from "../useContextInsightViewModel";

vi.mock("../../../../entities/trace/api/traceApi", () => ({
  fetchTraceList: vi.fn(),
  fetchTraceDetail: vi.fn(),
}));
vi.mock("../../../../entities/group/api/groupApi", () => ({ fetchDistinctGroups: vi.fn() }));

const first: TraceRecord = {
  trace_id: "example-a",
  group_id: "group-a",
  group_name: "示例群聊",
  platform: "telegram",
  trigger_type: "manual",
  status: "succeeded",
  started_at: 100,
  raw_message_count: 30,
  cleaned_message_count: 20,
  total_tokens: 100,
};
const second: TraceRecord = {
  ...first,
  trace_id: "example-b",
  raw_message_count: 0,
  cleaned_message_count: 0,
  total_tokens: 0,
};
const detail: TraceRecord = {
  ...first,
  token_usage: {
    trace_id: first.trace_id,
    prompt_tokens: 80,
    completion_tokens: 20,
    total_tokens: 100,
    estimated_cost: 0,
    per_analyzer: {},
  },
  context_metrics: {
    trace_id: first.trace_id,
    raw_message_count: 30,
    cleaned_message_count: 20,
    compression_ratio: 2 / 3,
    incremental_batches: 3,
    window_size: 10,
  },
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((done, fail) => {
    resolve = done;
    reject = fail;
  });
  return { promise, resolve, reject };
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.mocked(fetchTraceList).mockResolvedValue({ items: [first, second], total: 2 });
  vi.mocked(fetchTraceDetail).mockImplementation(async (id) =>
    id === first.trace_id ? detail : second,
  );
  vi.mocked(fetchDistinctGroups).mockResolvedValue([]);
});
afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
});

it("切换任务立即隔离上一项明细，迟到成功不能覆盖当前任务", async () => {
  const late = deferred<TraceRecord | null>();
  vi.mocked(fetchTraceDetail).mockReturnValueOnce(late.promise);
  const { result } = renderHook(useContextInsightViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.detailLoading).toBe(true);
  await act(async () => result.current.setSelectedTrace(second));
  expect(result.current.selectedTrace).toEqual(second);
  expect(result.current.tokenUsage).toBeNull();
  expect(result.current.contextMetrics.raw_message_count).toBe(0);
  expect(result.current.contextMetrics.incremental_batches).toBeUndefined();
  await act(async () => late.resolve(detail));
  expect(result.current.tokenUsage).toBeNull();
  expect(result.current.contextMetrics.raw_message_count).toBe(0);
});

it("已有明细在选择变化时也不串用，旧错误不污染新任务或卸载视图", async () => {
  const { result, unmount } = renderHook(useContextInsightViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.tokenUsage).toEqual(detail.token_usage);
  const late = deferred<TraceRecord | null>();
  vi.mocked(fetchTraceDetail).mockReturnValueOnce(late.promise);
  act(() => result.current.setSelectedTrace(second));
  expect(result.current.tokenUsage).toBeNull();
  await act(async () => result.current.setSelectedTrace(first));
  await act(async () => late.reject(new Error("上一项失败")));
  expect(result.current.detailError).toBe("");
  expect(result.current.tokenUsage).toEqual(detail.token_usage);
  const closing = deferred<TraceRecord | null>();
  vi.mocked(fetchTraceDetail).mockReturnValueOnce(closing.promise);
  act(() => result.current.refresh());
  unmount();
  await act(async () => closing.reject(new Error("卸载后失败")));
  expect(vi.getTimerCount()).toBe(0);
});

it("详情缺失或错编号不会补零，刷新失败保留同一任务的已读数据", async () => {
  const { result } = renderHook(useContextInsightViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  vi.mocked(fetchTraceDetail).mockRejectedValueOnce(new Error("连接失败"));
  act(() => result.current.refresh(false));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(fetchTraceDetail).toHaveBeenLastCalledWith(first.trace_id, true);
  expect(result.current.detailError).toContain("连接失败");
  expect(result.current.tokenUsage).toEqual(detail.token_usage);
  vi.mocked(fetchTraceDetail).mockResolvedValueOnce(null);
  act(() => result.current.refresh());
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.detailError).toContain("未找到");
  expect(result.current.tokenUsage).toBeNull();
  expect(result.current.contextMetrics.window_size).toBeUndefined();
  vi.mocked(fetchTraceDetail).mockResolvedValueOnce(second);
  act(() => result.current.refresh());
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.detailError).toContain("任务编号不一致");
  expect(result.current.selectedTrace?.trace_id).toBe(first.trace_id);
  expect(result.current.tokenUsage).toBeNull();
});

it("搜索防抖立即废弃旧列表，空结果清理当前统计", async () => {
  const late = deferred<Awaited<ReturnType<typeof fetchTraceList>>>();
  vi.mocked(fetchTraceList).mockReturnValueOnce(late.promise);
  const { result } = renderHook(useContextInsightViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  act(() => result.current.setSearch("摄"));
  await act(async () => late.resolve({ items: [first], total: 1 }));
  expect(result.current.traces).toEqual([]);
  act(() => result.current.setSearch(" 摄影 "));
  await act(async () => vi.advanceTimersByTimeAsync(249));
  expect(fetchTraceList).toHaveBeenCalledTimes(1);
  await act(async () => vi.advanceTimersByTimeAsync(1));
  expect(fetchTraceList).toHaveBeenLastCalledWith(expect.objectContaining({ search: "摄影" }));
  expect(result.current.tokenUsage).toEqual(detail.token_usage);
  vi.mocked(fetchTraceList).mockResolvedValueOnce({ items: [], total: 0 });
  act(() => result.current.setStatusFilter("failed"));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.selectedTrace).toBeNull();
  expect(result.current.tokenUsage).toBeNull();
  expect(result.current.contextMetrics.raw_message_count).toBeUndefined();
});

it("刷新保留筛选和当前选择，列表与群聊错误可以恢复而不清空已有数据", async () => {
  const { result } = renderHook(useContextInsightViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  act(() => {
    result.current.setSelectedTrace(second);
    result.current.setSelectedGroup("group-a");
    result.current.setDateRange([100, 200]);
  });
  await act(async () => vi.advanceTimersByTimeAsync(0));
  vi.mocked(fetchTraceList).mockRejectedValueOnce(new Error("宿主未响应"));
  vi.mocked(fetchDistinctGroups).mockRejectedValueOnce(new Error("群聊不可用"));
  act(() => result.current.refresh());
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.selectedTrace?.trace_id).toBe(second.trace_id);
  expect(result.current.traces).toHaveLength(2);
  expect(result.current.error).toContain("宿主未响应");
  expect(result.current.groupsError).toContain("群聊不可用");
  expect(fetchTraceList).toHaveBeenLastCalledWith(
    expect.objectContaining({ group_id: "group-a", start_time: 100, end_time: 200 }),
  );
  act(() => result.current.refresh(false));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.error).toBe("");
  expect(result.current.groupsError).toBe("");
  act(() => result.current.resetFilters());
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.dateRange).toBeNull();
  expect(result.current.selectedGroup).toBeUndefined();
  expect(result.current.selectedTrace?.trace_id).toBe(second.trace_id);
});
it("继续加载使用最后一条游标，追加去重并保留选择，刷新移出范围时明确标记", async () => {
  vi.mocked(fetchTraceList).mockResolvedValueOnce({
    items: [first, second],
    total: 60,
    has_more: true,
  });
  const { result } = renderHook(useContextInsightViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  act(() => result.current.setSelectedTrace(second));
  const older = { ...first, trace_id: "older", started_at: 90 };
  vi.mocked(fetchTraceList).mockResolvedValueOnce({
    items: [second, older],
    total: 1,
    has_more: false,
  });
  await act(async () => result.current.loadMore());
  expect(fetchTraceList).toHaveBeenLastCalledWith(
    expect.objectContaining({ before_time: 100, before_id: second.trace_id }),
  );
  expect(result.current.traces.map((item) => item.trace_id)).toEqual([
    first.trace_id,
    second.trace_id,
    older.trace_id,
  ]);
  expect(result.current.selectedTrace?.trace_id).toBe(second.trace_id);
  expect(result.current.total).toBe(60);
  expect(result.current.hasMore).toBe(false);
  vi.mocked(fetchTraceList).mockResolvedValueOnce({ items: [first], total: 1 });
  act(() => result.current.refresh(false));
  await act(async () => vi.advanceTimersByTimeAsync(0));
  expect(result.current.selectedTrace).toBeNull();
  expect(result.current.selectionMissing).toBe(true);
  await act(async () => result.current.setSelectedTrace(first));
  expect(result.current.selectionMissing).toBe(false);
});

it("继续加载防重入，失败可重试，改筛选和卸载会废弃迟到追加", async () => {
  vi.mocked(fetchTraceList).mockResolvedValueOnce({ items: [first], total: 60, has_more: true });
  const { result, unmount } = renderHook(useContextInsightViewModel);
  await act(async () => vi.advanceTimersByTimeAsync(0));
  vi.mocked(fetchTraceList).mockRejectedValueOnce(new Error("断网"));
  await act(async () => result.current.loadMore());
  expect(result.current.moreError).toContain("重试");
  expect(result.current.traces).toEqual([first]);
  const late = deferred<Awaited<ReturnType<typeof fetchTraceList>>>();
  vi.mocked(fetchTraceList).mockReturnValueOnce(late.promise);
  act(() => {
    void result.current.loadMore();
    void result.current.loadMore();
  });
  expect(fetchTraceList).toHaveBeenCalledTimes(3);
  act(() => result.current.setSearch("新的筛选"));
  await act(async () => late.resolve({ items: [{ ...second, trace_id: "late" }], total: 1 }));
  expect(result.current.traces.some((item) => item.trace_id === "late")).toBe(false);
  unmount();
  expect(vi.getTimerCount()).toBe(0);
});
