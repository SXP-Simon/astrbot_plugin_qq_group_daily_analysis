import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { fetchTraceDetail } from "../../../../entities/trace/api/traceApi";
import { fetchTraceLogs } from "../../../../entities/log/api/logApi";
import type { TraceRecord } from "../../../../entities/trace/model/types";
import { useTraceDetail } from "../useTraceDetail";

vi.mock("../../../../entities/trace/api/traceApi", () => ({ fetchTraceDetail: vi.fn() }));
vi.mock("../../../../entities/log/api/logApi", () => ({ fetchTraceLogs: vi.fn() }));

const completed: TraceRecord = {
  trace_id: "example-a",
  group_id: "group-a",
  group_name: "示例群聊",
  platform: "telegram",
  trigger_type: "manual",
  status: "succeeded",
  started_at: 100,
  duration_ms: null,
};

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.mocked(fetchTraceDetail).mockResolvedValue(completed);
  vi.mocked(fetchTraceLogs).mockResolvedValue([]);
});
afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
});

it("快速切换任务后，旧详情和日志不能覆盖新任务", async () => {
  const first = deferred<TraceRecord | null>();
  vi.mocked(fetchTraceDetail).mockReturnValueOnce(first.promise);
  const view = renderHook(({ id }) => useTraceDetail(id, true), {
    initialProps: { id: "example-a" },
  });
  vi.mocked(fetchTraceDetail).mockResolvedValue({ ...completed, trace_id: "example-b" });
  await act(async () => view.rerender({ id: "example-b" }));
  await act(async () => first.resolve(completed));
  expect(view.result.current.trace?.trace_id).toBe("example-b");
  expect(view.result.current.loading).toBe(false);
  expect(view.result.current.error).toBeNull();
  view.unmount();
});

it("关闭后迟到的运行中响应不能恢复视图或重新启动轮询", async () => {
  const first = deferred<TraceRecord | null>();
  vi.mocked(fetchTraceDetail).mockReturnValueOnce(first.promise);
  const view = renderHook(({ open }) => useTraceDetail("example-a", open), {
    initialProps: { open: true },
  });
  view.rerender({ open: false });
  await act(async () => first.resolve({ ...completed, status: "running" }));
  await act(async () => vi.advanceTimersByTimeAsync(10000));
  expect(view.result.current.trace).toBeNull();
  expect(view.result.current.logs).toEqual([]);
  expect(fetchTraceDetail).toHaveBeenCalledTimes(1);
  expect(vi.getTimerCount()).toBe(0);
  view.unmount();
});

it("卸载运行中详情会取消已安排的轮询", async () => {
  vi.mocked(fetchTraceDetail).mockResolvedValue({ ...completed, status: "running" });
  const view = renderHook(() => useTraceDetail("example-a", true));
  await act(async () => {});
  expect(vi.getTimerCount()).toBe(1);
  view.unmount();
  expect(vi.getTimerCount()).toBe(0);
  await act(async () => vi.advanceTimersByTimeAsync(10000));
  expect(fetchTraceDetail).toHaveBeenCalledTimes(1);
});

it("每轮请求结束后才轮询，终态停止，缺失耗时不被当前时间补写", async () => {
  const poll = deferred<TraceRecord | null>();
  vi.mocked(fetchTraceDetail)
    .mockResolvedValueOnce({ ...completed, status: "running" })
    .mockReturnValueOnce(poll.promise);
  const view = renderHook(() => useTraceDetail("example-a", true));
  await act(async () => {});
  expect(view.result.current.trace?.duration_ms).toBeNull();
  await act(async () => vi.advanceTimersByTimeAsync(10000));
  expect(fetchTraceDetail).toHaveBeenCalledTimes(2);
  expect(fetchTraceDetail).toHaveBeenLastCalledWith("example-a", true);
  await act(async () => poll.resolve(completed));
  await act(async () => vi.advanceTimersByTimeAsync(10000));
  expect(fetchTraceDetail).toHaveBeenCalledTimes(2);
  expect(vi.getTimerCount()).toBe(0);
  view.unmount();
});

it("刷新绕过详情缓存，刷新前发出的请求不能覆盖新结果", async () => {
  const first = deferred<TraceRecord | null>();
  vi.mocked(fetchTraceDetail).mockReturnValueOnce(first.promise);
  const view = renderHook(() => useTraceDetail("example-a", true));
  await act(async () => view.result.current.refresh());
  expect(fetchTraceDetail).toHaveBeenLastCalledWith("example-a", true);
  await act(async () => first.resolve({ ...completed, status: "running" }));
  expect(view.result.current.trace?.status).toBe("succeeded");
  expect(view.result.current.refreshing).toBe(false);
  expect(vi.getTimerCount()).toBe(0);
  view.unmount();
});

it("日志失败不遮挡详情，刷新成功后清除提示", async () => {
  vi.mocked(fetchTraceLogs).mockRejectedValueOnce(new Error("离线"));
  const view = renderHook(() => useTraceDetail("example-a", true));
  await act(async () => {});
  expect(view.result.current.trace).toEqual(completed);
  expect(view.result.current.error).toBeNull();
  expect(view.result.current.logsError).toContain("日志暂时无法加载");
  await act(async () => view.result.current.refresh());
  expect(view.result.current.logsError).toBeNull();
  view.unmount();
});

it("轮询失败保留上次详情并允许恢复，卸载后清理定时器", async () => {
  vi.mocked(fetchTraceDetail)
    .mockResolvedValueOnce({ ...completed, status: "running" })
    .mockRejectedValueOnce(new Error("网络失败"))
    .mockResolvedValueOnce(completed);
  const view = renderHook(() => useTraceDetail("example-a", true));
  await act(async () => {});
  await act(async () => vi.advanceTimersByTimeAsync(1500));
  expect(view.result.current.trace?.status).toBe("running");
  expect(view.result.current.error).toContain("暂时无法更新");
  await act(async () => vi.advanceTimersByTimeAsync(1500));
  expect(view.result.current.trace?.status).toBe("succeeded");
  expect(view.result.current.error).toBeNull();
  view.unmount();
  expect(vi.getTimerCount()).toBe(0);
});

it("最终失败不能被历史警告覆盖，成功任务仍标注阶段警告", async () => {
  vi.mocked(fetchTraceDetail).mockResolvedValueOnce({
    ...completed,
    status: "failed",
    extra: { has_warnings: true },
  });
  const view = renderHook(() => useTraceDetail("example-a", true));
  await act(async () => {});
  expect(view.result.current.effectiveStatus).toBe("failed");
  vi.mocked(fetchTraceDetail).mockResolvedValueOnce({
    ...completed,
    extra: { has_warnings: true },
  });
  await act(async () => view.result.current.refresh());
  expect(view.result.current.effectiveStatus).toBe("warning");
  view.unmount();
});

it("记录不存在时显示明确提示，关闭状态不请求", async () => {
  vi.mocked(fetchTraceDetail).mockResolvedValueOnce(null);
  const view = renderHook(({ open }) => useTraceDetail("example-a", open), {
    initialProps: { open: false },
  });
  expect(fetchTraceDetail).not.toHaveBeenCalled();
  await act(async () => view.rerender({ open: true }));
  expect(view.result.current.error).toContain("没有找到");
  expect(view.result.current.loading).toBe(false);
  view.unmount();
});
