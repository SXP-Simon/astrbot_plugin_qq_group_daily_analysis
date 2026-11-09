import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useLogsViewModel } from "@/pages/logs/model/useLogsViewModel";
import { fetchPluginLogs, clearPluginLogs } from "@/entities/log/api/logApi";
import { subscribeSSE } from "@/shared/api/bridge";
import { copyToClipboard } from "@/shared/lib/clipboard";
import type { PluginLogItem } from "@/entities/log/model/types";

vi.mock("@/entities/log/api/logApi", () => ({
  fetchPluginLogs: vi.fn(),
  clearPluginLogs: vi.fn(),
}));
vi.mock("@/shared/api/bridge", () => ({ subscribeSSE: vi.fn() }));
vi.mock("@/shared/lib/clipboard", () => ({ copyToClipboard: vi.fn() }));

const entry: PluginLogItem = {
  id: "example-log",
  timestamp: 100,
  time_str: "2026-11-07 12:00:00.000",
  level: "INFO",
  logger_name: "Render",
  tag: "Render",
  message: "示例渲染完成",
  raw: "[INFO] 示例渲染完成",
  trace_id: "example-trace",
  location: "render:20",
};

it("函数名搜索也作用于实时日志，解析后保留定位字段", async () => {
  const { result } = renderHook(() => useLogsViewModel());
  await act(async () => result.current.setSearch("Renderer.generate"));
  const receive = vi.mocked(subscribeSSE).mock.lastCall![0].onMessage;
  act(() => {
    receive({
      event: "log_entry",
      data: { ...entry, id: "matched", function_name: "Renderer.generate" },
    });
    receive({
      event: "log_entry",
      data: { ...entry, id: "unmatched", function_name: "Renderer.close" },
    });
  });
  expect(result.current.logs).toEqual([
    expect.objectContaining({
      id: "matched",
      function_name: "Renderer.generate",
      location: "render:20",
    }),
  ]);
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.mocked(fetchPluginLogs).mockResolvedValue({ items: [], total: 0, available_tags: [] });
  vi.mocked(clearPluginLogs).mockResolvedValue(undefined);
});

it("重复 SSE 不增加计数，查询返回后保留期间到达的日志，错误结构不会破坏页面", async () => {
  const pending = deferred<Awaited<ReturnType<typeof fetchPluginLogs>>>();
  vi.mocked(fetchPluginLogs).mockReturnValueOnce(pending.promise);
  const { result } = renderHook(() => useLogsViewModel());
  const receive = vi.mocked(subscribeSSE).mock.lastCall![0].onMessage;
  act(() => {
    receive({ event: "log_entry", data: { id: "malformed" } });
    receive({ event: "log_entry", data: entry });
    receive({ event: "log_entry", data: entry });
  });
  expect(result.current.total).toBe(1);
  expect(result.current.logs).toEqual([entry]);
  await act(async () => pending.resolve({ items: [], total: 0, available_tags: [] }));
  expect(result.current.logs).toEqual([entry]);
  expect(result.current.total).toBe(1);
});

it("轮询不会重叠慢请求，暂停后迟到响应与旧订阅不再更新页面", async () => {
  const pending = deferred<Awaited<ReturnType<typeof fetchPluginLogs>>>();
  vi.mocked(fetchPluginLogs).mockReturnValueOnce(pending.promise);
  const unsubscribe = vi.fn();
  vi.mocked(subscribeSSE).mockReturnValue(unsubscribe);
  const { result } = renderHook(() => useLogsViewModel());
  const receive = vi.mocked(subscribeSSE).mock.lastCall![0].onMessage;
  await act(async () => vi.advanceTimersByTimeAsync(15000));
  expect(fetchPluginLogs).toHaveBeenCalledTimes(1);
  act(() => result.current.setAutoRefresh(false));
  expect(unsubscribe).toHaveBeenCalled();
  await act(async () => {
    pending.resolve({ items: [entry], total: 1, available_tags: [] });
    receive({ event: "log_entry", data: entry });
  });
  expect(result.current.logs).toEqual([]);
  await act(async () => {
    await result.current.refresh(true);
    await vi.advanceTimersByTimeAsync(5000);
  });
  expect(fetchPluginLogs).toHaveBeenCalledTimes(1);
  await act(async () => result.current.refresh(false));
  expect(fetchPluginLogs).toHaveBeenCalledTimes(2);
  act(() => result.current.setAutoRefresh(true));
  await act(async () => vi.advanceTimersByTimeAsync(5000));
  expect(fetchPluginLogs).toHaveBeenCalledTimes(3);
});

it("实时日志沿用分类、级别、任务和搜索过滤，废弃旧筛选的订阅", async () => {
  const { result } = renderHook(() => useLogsViewModel());
  const oldReceive = vi.mocked(subscribeSSE).mock.lastCall![0].onMessage;
  await act(async () => {
    result.current.setLevel("WARNING");
    result.current.setTag("Render");
    result.current.setTraceId("example-trace");
    result.current.setSearch("render:20");
  });
  const receive = vi.mocked(subscribeSSE).mock.lastCall![0].onMessage;
  act(() => {
    oldReceive({ event: "log_entry", data: entry });
    receive({ event: "log_entry", data: entry });
    receive({ event: "log_entry", data: { ...entry, level: "WARNING", trace_id: "other" } });
    receive({ event: "log_entry", data: { ...entry, level: "WARNING", tag: "LLM" } });
    receive({ event: "log_entry", data: { ...entry, level: "WARNING", location: "other:1" } });
  });
  expect(result.current.logs).toEqual([]);
  act(() => receive({ event: "log_entry", data: { ...entry, level: "WARNING" } }));
  expect(result.current.logs).toHaveLength(1);
});

it("加载和清空失败保留日志并给出原因，复制只在实际成功后提示成功", async () => {
  vi.mocked(fetchPluginLogs).mockResolvedValue({ items: [entry], total: 1, available_tags: [] });
  const { result } = renderHook(() => useLogsViewModel());
  await act(async () => {});
  vi.mocked(fetchPluginLogs).mockRejectedValueOnce(new Error("连接中断"));
  await act(async () => result.current.refresh());
  expect(result.current.error).toContain("连接中断");
  expect(result.current.logs).toEqual([entry]);
  vi.mocked(clearPluginLogs).mockRejectedValueOnce(new Error("没有权限"));
  await act(async () => expect(await result.current.clearLogs()).toBe(false));
  expect(result.current.logs).toEqual([entry]);
  expect(result.current.error).toContain("没有权限");
  expect(result.current.feedback).not.toContain("已清空");
  vi.mocked(copyToClipboard).mockResolvedValueOnce(false).mockResolvedValueOnce(true);
  await act(async () => result.current.copyLogs());
  expect(result.current.feedback).toContain("复制失败");
  await act(async () => result.current.copyLogs());
  expect(copyToClipboard).toHaveBeenLastCalledWith(entry.raw);
  expect(result.current.feedback).toBe("已复制 1 条日志");
});

it("清空锁阻止重复提交和轮询，清空前的查询不会让旧日志复活", async () => {
  const old = deferred<Awaited<ReturnType<typeof fetchPluginLogs>>>();
  const clear = deferred<void>();
  vi.mocked(fetchPluginLogs).mockReturnValueOnce(old.promise);
  vi.mocked(clearPluginLogs).mockReturnValueOnce(clear.promise);
  const { result } = renderHook(() => useLogsViewModel());
  let operation!: Promise<boolean>;
  act(() => {
    operation = result.current.clearLogs();
  });
  await act(async () => {
    expect(await result.current.clearLogs()).toBe(false);
    await vi.advanceTimersByTimeAsync(10000);
  });
  expect(clearPluginLogs).toHaveBeenCalledTimes(1);
  expect(fetchPluginLogs).toHaveBeenCalledTimes(1);
  await act(async () => {
    clear.resolve();
    expect(await operation).toBe(true);
  });
  await act(async () => old.resolve({ items: [entry], total: 1, available_tags: [] }));
  expect(result.current.logs).toEqual([]);
  expect(result.current.total).toBe(0);
  expect(result.current.clearing).toBe(false);
  expect(result.current.feedback).toBe("日志缓冲已清空");
});
afterEach(() => {
  vi.useRealTimers();
  vi.resetAllMocks();
});

it("隐藏页不轮询或订阅，返回时保留筛选，离开后清理订阅和计时器", async () => {
  const unsubscribe = vi.fn();
  vi.mocked(subscribeSSE).mockReturnValue(unsubscribe);
  const view = renderHook(({ active }) => useLogsViewModel(active), {
    initialProps: { active: false },
  });
  await act(async () => {
    await vi.advanceTimersByTimeAsync(6000);
  });
  expect(fetchPluginLogs).not.toHaveBeenCalled();
  expect(subscribeSSE).not.toHaveBeenCalled();
  await act(async () => {
    view.rerender({ active: true });
  });
  await act(async () => {
    view.result.current.setSearch("渲染");
  });
  expect(fetchPluginLogs).toHaveBeenLastCalledWith(expect.objectContaining({ search: "渲染" }));
  view.rerender({ active: false });
  const calls = vi.mocked(fetchPluginLogs).mock.calls.length;
  await act(async () => {
    await vi.advanceTimersByTimeAsync(10000);
  });
  expect(fetchPluginLogs).toHaveBeenCalledTimes(calls);
  expect(unsubscribe).toHaveBeenCalled();
  expect(view.result.current.search).toBe("渲染");
  view.unmount();
  expect(vi.getTimerCount()).toBe(0);
});

it("离开后再返回时，旧请求不能覆盖新列表", async () => {
  let resolve!: (value: Awaited<ReturnType<typeof fetchPluginLogs>>) => void;
  vi.mocked(fetchPluginLogs).mockReturnValueOnce(
    new Promise((done) => {
      resolve = done;
    }),
  );
  vi.mocked(subscribeSSE).mockReturnValue(() => {});
  const view = renderHook(({ active }) => useLogsViewModel(active), {
    initialProps: { active: true },
  });
  view.rerender({ active: false });
  await act(async () => {
    view.rerender({ active: true });
  });
  await act(async () => {
    resolve({ items: [], total: 999, available_tags: [] });
  });
  expect(view.result.current.total).toBe(0);
  expect(view.result.current.loading).toBe(false);
  view.unmount();
});
