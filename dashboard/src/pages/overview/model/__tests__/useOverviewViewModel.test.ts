import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { fetchActiveTasks, cancelActiveTask } from "../../../../entities/task/api/taskApi";
import { fetchMetricsSummary } from "../../../../entities/metric/api/metricApi";
import { acknowledgeTrace, fetchTraceList } from "../../../../entities/trace/api/traceApi";
import type { ActiveTask } from "../../../../entities/task/model/types";
import { useOverviewViewModel } from "../useOverviewViewModel";
import { mockMetricsSummary } from "../../../../mocks/data/metrics";
import { mockTraces } from "../../../../mocks/data/traces";

vi.mock("../../../../entities/task/api/taskApi", () => ({
  fetchActiveTasks: vi.fn(),
  cancelActiveTask: vi.fn(),
}));
vi.mock("../../../../entities/metric/api/metricApi", () => ({ fetchMetricsSummary: vi.fn() }));
vi.mock("../../../../entities/trace/api/traceApi", () => ({
  fetchTraceList: vi.fn(),
  acknowledgeTrace: vi.fn(),
}));

const task: ActiveTask = {
  task_id: "WEB",
  group_id: "GROUP",
  group_name: "测试群",
  platform: "official",
  trigger_type: "web_ui",
  current_stage: "LLM_ANALYSIS",
  started_at: Date.now() / 1000,
  duration_s: 0,
  last_heartbeat: Date.now() / 1000,
};
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchActiveTasks).mockResolvedValue([task]);
  vi.mocked(fetchMetricsSummary).mockResolvedValue(mockMetricsSummary);
  vi.mocked(fetchTraceList).mockResolvedValue({ items: [], total: 0 });
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
});

it.each([true, false])("中止回执 %s 返回给确认弹窗，失败保留任务", async (accepted) => {
  vi.mocked(cancelActiveTask).mockResolvedValue(accepted);
  const { result } = renderHook(() => useOverviewViewModel());
  await waitFor(() => expect(result.current.tasksLoaded).toBe(true));
  await act(async () => {
    expect(await result.current.handleCancelTask("WEB")).toBe(accepted);
  });
  expect(cancelActiveTask).toHaveBeenCalledWith("WEB");
  expect(result.current.activeTasks).toHaveLength(accepted ? 0 : 1);
  expect(result.current.feedback).toBe(accepted ? "中止请求已接受，后台正在清理资源。" : "");
});

it.each(["task_canceled", "task_timed_out", "task_finished"])(
  "%s 及迟到进度不能复活已结束任务",
  async (event) => {
    const { result } = renderHook(() => useOverviewViewModel());
    await waitFor(() => expect(result.current.tasksLoaded).toBe(true));
    const old = deferred<ActiveTask[]>();
    vi.mocked(fetchActiveTasks).mockReturnValueOnce(old.promise);
    let oldRequest!: Promise<void>;
    act(() => {
      oldRequest = result.current.refresh();
    });
    act(() => result.current.handleSSEEvent({ event, data: { task_id: "WEB" } }));
    expect(result.current.activeTasks).toEqual([]);
    await act(async () => {
      old.resolve([task]);
      await oldRequest;
    });
    act(() => result.current.handleSSEEvent({ event: "task_progress", data: task }));
    expect(result.current.activeTasks).toEqual([]);
  },
);

it.each(["initial_state", "task_started", "task_progress"])(
  "查询期间的 %s 优先于旧快照，统计仍能加载",
  async (event) => {
    const old = deferred<ActiveTask[]>();
    vi.mocked(fetchActiveTasks).mockReturnValueOnce(old.promise);
    const { result } = renderHook(() => useOverviewViewModel());
    const updated = { ...task, current_stage: "RENDER_REPORT" };
    act(() =>
      result.current.handleSSEEvent({
        event,
        data: event === "initial_state" ? [updated] : updated,
      }),
    );
    await act(async () => old.resolve([task]));
    expect(result.current.activeTasks[0].current_stage).toBe("RENDER_REPORT");
    expect(result.current.metrics).toEqual(mockMetricsSummary);
    expect(result.current.loading).toBe(false);
  },
);

it("部分接口失败不隐藏其他数据，刷新失败保留上次结果", async () => {
  vi.mocked(fetchMetricsSummary).mockRejectedValueOnce(new Error("离线"));
  const { result } = renderHook(() => useOverviewViewModel());
  await waitFor(() => expect(result.current.loading).toBe(false));
  expect(result.current.activeTasks).toEqual([task]);
  expect(result.current.metrics).toBeNull();
  expect(result.current.errors.metrics).toContain("未能更新");
  vi.mocked(fetchActiveTasks).mockRejectedValueOnce(new Error("离线"));
  await act(() => result.current.refresh(false));
  expect(result.current.activeTasks).toEqual([task]);
  expect(result.current.errors.tasks).toContain("未能更新");
  expect(result.current.metrics).toEqual(mockMetricsSummary);
});

it("无效事件不影响列表，取消请求不重叠且异常可重试", async () => {
  const { result } = renderHook(() => useOverviewViewModel());
  await waitFor(() => expect(result.current.tasksLoaded).toBe(true));
  for (const event of [
    null,
    { event: "task_progress", data: { task_id: "WEB" } },
    { event: "initial_state", data: [null] },
    { event: "task_finished", data: {} },
  ]) {
    act(() => result.current.handleSSEEvent(event));
  }
  expect(result.current.activeTasks).toEqual([task]);
  const cancel = deferred<boolean>();
  vi.mocked(cancelActiveTask)
    .mockReturnValueOnce(cancel.promise)
    .mockRejectedValueOnce(new Error("离线"));
  let first!: Promise<boolean>;
  act(() => {
    first = result.current.handleCancelTask("WEB");
  });
  await act(async () => expect(await result.current.handleCancelTask("WEB")).toBe(false));
  expect(cancelActiveTask).toHaveBeenCalledOnce();
  await act(async () => {
    cancel.resolve(false);
    await first;
  });
  await act(async () => expect(await result.current.handleCancelTask("WEB")).toBe(false));
  expect(result.current.activeTasks).toEqual([task]);
});

it("隐藏时停止计时与请求，旧响应和卸载后事件失效，返回重取", async () => {
  vi.useFakeTimers();
  const valid = { ...task, started_at: Date.now() / 1000 - 10 };
  vi.mocked(fetchActiveTasks).mockResolvedValue([
    valid,
    { ...task, task_id: "unknown", started_at: 0, duration_s: -1 },
  ]);
  const { result, rerender, unmount } = renderHook(({ active }) => useOverviewViewModel(active), {
    initialProps: { active: true },
  });
  await act(async () => {});
  act(() => vi.advanceTimersByTime(1000));
  expect(result.current.activeTasks[0].duration_s).toBe(11);
  expect(result.current.activeTasks[1].duration_s).toBe(-1);
  const old = deferred<ActiveTask[]>();
  vi.mocked(fetchActiveTasks).mockReturnValueOnce(old.promise);
  act(() => {
    void result.current.refresh(false);
  });
  rerender({ active: false });
  const snapshot = result.current.activeTasks;
  await act(async () => {
    old.resolve([]);
  });
  act(() => vi.advanceTimersByTime(10000));
  expect(result.current.activeTasks).toEqual(snapshot);
  const count = vi.mocked(fetchActiveTasks).mock.calls.length;
  await act(() => result.current.refresh());
  expect(fetchActiveTasks).toHaveBeenCalledTimes(count);
  rerender({ active: true });
  await act(async () => {});
  expect(fetchActiveTasks).toHaveBeenCalledTimes(count + 1);
  unmount();
  act(() => result.current.handleSSEEvent({ event: "task_finished", data: { task_id: "WEB" } }));
  expect(fetchActiveTasks).toHaveBeenCalledTimes(count + 1);
});

it("关注列表只根据明确结果和警告标记，不将正常取消误报为失败", async () => {
  const base = mockTraces[0];
  vi.mocked(fetchTraceList).mockResolvedValue({
    items: [
      { ...base, trace_id: "failed", status: "failed" },
      { ...base, trace_id: "warning", status: "warning" },
      { ...base, trace_id: "recovered", status: "succeeded", extra: { has_warnings: true } },
      { ...base, trace_id: "cancelled", status: "aborted" },
      { ...base, trace_id: "ok", status: "succeeded", extra: {} },
    ],
    total: 5,
  });
  const { result } = renderHook(() => useOverviewViewModel());
  await waitFor(() => expect(result.current.loading).toBe(false));
  expect(result.current.attentionTraces.map((trace) => trace.trace_id)).toEqual([
    "failed",
    "warning",
    "recovered",
  ]);
  expect(fetchTraceList).toHaveBeenCalledWith({
    limit: 20,
    offset: 0,
    sort_by: "started_at",
    sort_order: "desc",
  });
});

it("知晓保存后收起、可显示和恢复，迟到的旧查询不能覆盖标记", async () => {
  const trace = {
    ...mockTraces.find((item) => item.status === "failed")!,
    acknowledged_at: null as number | null,
  };
  vi.mocked(fetchTraceList).mockImplementation(async () => ({ items: [{ ...trace }], total: 1 }));
  vi.mocked(acknowledgeTrace).mockImplementation(async (traceId, known) => {
    trace.acknowledged_at = known ? 123 : null;
    return { trace_id: traceId, acknowledged_at: trace.acknowledged_at };
  });
  const { result } = renderHook(() => useOverviewViewModel());
  await waitFor(() => expect(result.current.attentionTraces).toHaveLength(1));
  const old = deferred<Awaited<ReturnType<typeof fetchTraceList>>>();
  vi.mocked(fetchTraceList).mockReturnValueOnce(old.promise);
  let request!: Promise<void>;
  act(() => {
    request = result.current.refresh();
  });
  await act(async () => {
    await result.current.handleAcknowledge(trace.trace_id, true);
  });
  expect(result.current.attentionTraces).toHaveLength(0);
  expect(result.current.acknowledgedCount).toBe(1);
  await act(async () => {
    old.resolve({ items: [{ ...trace, acknowledged_at: null }], total: 1 });
    await request;
  });
  expect(result.current.attentionTraces).toHaveLength(0);
  act(() => result.current.setShowAcknowledged(true));
  expect(result.current.attentionTraces[0]).toMatchObject({
    status: "failed",
    acknowledged_at: 123,
  });
  await act(async () => {
    await result.current.handleAcknowledge(trace.trace_id, false);
  });
  expect(result.current.acknowledgedCount).toBe(0);
  expect(result.current.attentionTraces[0].acknowledged_at).toBeNull();
});

it("保存期间禁止重复提交，失败保留原提醒并提示重试", async () => {
  const trace = { ...mockTraces.find((item) => item.status === "failed")!, acknowledged_at: null };
  vi.mocked(fetchTraceList).mockResolvedValue({ items: [trace], total: 1 });
  let reject!: (reason: Error) => void;
  vi.mocked(acknowledgeTrace).mockReturnValue(
    new Promise((_done, fail) => {
      reject = fail;
    }),
  );
  const { result } = renderHook(() => useOverviewViewModel());
  await waitFor(() => expect(result.current.attentionTraces).toHaveLength(1));
  let pending!: Promise<void>;
  act(() => {
    pending = result.current.handleAcknowledge(trace.trace_id, true);
  });
  expect(result.current.acknowledgingIds).toEqual([trace.trace_id]);
  await act(async () => {
    await result.current.handleAcknowledge(trace.trace_id, true);
  });
  expect(acknowledgeTrace).toHaveBeenCalledTimes(1);
  await act(async () => {
    reject(new Error("disk full"));
    await pending;
  });
  expect(result.current.attentionTraces).toHaveLength(1);
  expect(result.current.acknowledgementError).toContain("未能保存");
  expect(result.current.acknowledgingIds).toEqual([]);
});

it("重新进入总览读取已保存的标记，卸载后迟到回执不触发刷新", async () => {
  const trace = { ...mockTraces.find((item) => item.status === "failed")!, acknowledged_at: 123 };
  vi.mocked(fetchTraceList).mockResolvedValue({ items: [trace], total: 1 });
  const pending = deferred<Awaited<ReturnType<typeof acknowledgeTrace>>>();
  vi.mocked(acknowledgeTrace).mockReturnValue(pending.promise);
  const { result, unmount } = renderHook(() => useOverviewViewModel());
  await waitFor(() => expect(result.current.acknowledgedCount).toBe(1));
  expect(result.current.attentionTraces).toHaveLength(0);
  let saving!: Promise<void>;
  act(() => {
    saving = result.current.handleAcknowledge(trace.trace_id, false);
  });
  const calls = vi.mocked(fetchTraceList).mock.calls.length;
  unmount();
  await act(async () => {
    pending.resolve({ trace_id: trace.trace_id, acknowledged_at: null });
    await saving;
  });
  expect(fetchTraceList).toHaveBeenCalledTimes(calls);
});

it("连续勾选不同任务只提交保存，不额外读取任务、统计或历史", async () => {
  const traces = ["a", "b", "c"].map((trace_id) => ({
    ...mockTraces[0],
    trace_id,
    status: "failed" as const,
    acknowledged_at: null,
  }));
  vi.mocked(fetchTraceList).mockResolvedValue({ items: traces, total: traces.length });
  vi.mocked(acknowledgeTrace).mockImplementation(async (trace_id, known) => ({
    trace_id,
    acknowledged_at: known ? 123 : null,
  }));
  const { result } = renderHook(() => useOverviewViewModel());
  await waitFor(() => expect(result.current.attentionTraces).toHaveLength(3));
  for (const trace of traces)
    await act(() => result.current.handleAcknowledge(trace.trace_id, true));
  expect(result.current.acknowledgedCount).toBe(3);
  expect(result.current.attentionTraces).toHaveLength(0);
  await act(() => result.current.handleAcknowledge("b", false));
  expect(result.current.attentionTraces.map((trace) => trace.trace_id)).toEqual(["b"]);
  expect(acknowledgeTrace).toHaveBeenCalledTimes(4);
  expect(fetchActiveTasks).toHaveBeenCalledTimes(1);
  expect(fetchMetricsSummary).toHaveBeenCalledTimes(1);
  expect(fetchTraceList).toHaveBeenCalledTimes(1);
});

it("并发保存回执乱序时，旧查询保留全部知晓结果，同时接收新任务和统计", async () => {
  const traces = ["a", "b"].map((trace_id) => ({
    ...mockTraces[0],
    trace_id,
    status: "failed" as const,
    acknowledged_at: null,
  }));
  vi.mocked(fetchTraceList).mockResolvedValue({ items: traces, total: 2 });
  const { result } = renderHook(() => useOverviewViewModel());
  await waitFor(() => expect(result.current.attentionTraces).toHaveLength(2));
  const old = deferred<Awaited<ReturnType<typeof fetchTraceList>>>();
  vi.mocked(fetchTraceList).mockReturnValueOnce(old.promise);
  const updated = { ...mockMetricsSummary, total_traces: 999 };
  vi.mocked(fetchMetricsSummary).mockResolvedValueOnce(updated);
  let refresh!: Promise<void>;
  act(() => {
    refresh = result.current.refresh();
  });
  const a = deferred<Awaited<ReturnType<typeof acknowledgeTrace>>>();
  const b = deferred<Awaited<ReturnType<typeof acknowledgeTrace>>>();
  vi.mocked(acknowledgeTrace).mockReturnValueOnce(a.promise).mockReturnValueOnce(b.promise);
  let saveA!: Promise<void>;
  let saveB!: Promise<void>;
  act(() => {
    saveA = result.current.handleAcknowledge("a", true);
    saveB = result.current.handleAcknowledge("b", true);
  });
  await act(async () => {
    b.resolve({ trace_id: "b", acknowledged_at: 22 });
    await saveB;
  });
  await act(async () => {
    a.resolve({ trace_id: "a", acknowledged_at: 11 });
    await saveA;
  });
  const newTrace = { ...traces[0], trace_id: "new" };
  await act(async () => {
    old.resolve({ items: [newTrace, ...traces], total: 3 });
    await refresh;
  });
  expect(result.current.attentionTraces.map((trace) => trace.trace_id)).toEqual(["new"]);
  expect(result.current.acknowledgedCount).toBe(2);
  expect(result.current.metrics).toEqual(updated);
  expect(fetchTraceList).toHaveBeenCalledTimes(2);
  // 保存之后启动的查询读取数据库新状态，不永久覆盖其他页面的后续修改。
  vi.mocked(fetchTraceList).mockResolvedValue({ items: traces, total: 2 });
  await act(() => result.current.refresh());
  expect(result.current.acknowledgedCount).toBe(0);
});

it("旧查询期间先知晓再撤销，null 回执也不会被旧的知晓时间覆盖", async () => {
  const trace = {
    ...mockTraces[0],
    trace_id: "a",
    status: "failed" as const,
    acknowledged_at: null,
  };
  vi.mocked(fetchTraceList).mockResolvedValue({ items: [trace], total: 1 });
  vi.mocked(acknowledgeTrace).mockImplementation(async (trace_id, known) => ({
    trace_id,
    acknowledged_at: known ? 123 : null,
  }));
  const { result } = renderHook(() => useOverviewViewModel());
  await waitFor(() => expect(result.current.attentionTraces).toHaveLength(1));
  const old = deferred<Awaited<ReturnType<typeof fetchTraceList>>>();
  vi.mocked(fetchTraceList).mockReturnValueOnce(old.promise);
  let refresh!: Promise<void>;
  act(() => {
    refresh = result.current.refresh();
  });
  await act(() => result.current.handleAcknowledge("a", true));
  await act(() => result.current.handleAcknowledge("a", false));
  await act(async () => {
    old.resolve({ items: [{ ...trace, acknowledged_at: 123 }], total: 1 });
    await refresh;
  });
  expect(result.current.attentionTraces[0].acknowledged_at).toBeNull();
  expect(result.current.acknowledgedCount).toBe(0);
});
