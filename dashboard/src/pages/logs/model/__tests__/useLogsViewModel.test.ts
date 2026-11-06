import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { useLogsViewModel } from "../useLogsViewModel";
import { fetchPluginLogs } from "../../../../entities/log/api/logApi";
import { subscribeSSE } from "../../../../shared/api/bridge";

vi.mock("../../../../entities/log/api/logApi", () => ({
  fetchPluginLogs: vi.fn(),
  clearPluginLogs: vi.fn(),
}));
vi.mock("../../../../shared/api/bridge", () => ({ subscribeSSE: vi.fn() }));

beforeEach(() => {
  vi.useFakeTimers();
  vi.mocked(fetchPluginLogs).mockResolvedValue({ items: [], total: 0, available_tags: [] });
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
