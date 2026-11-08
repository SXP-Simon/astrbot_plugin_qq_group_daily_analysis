import { afterEach, expect, it, vi } from "vitest";
import { subscribeSSE, type AstrBotPluginPageBridge } from "../bridge";

afterEach(() => {
  delete window.AstrBotPluginPage;
});

it("提前离开后撤销迟到的宿主订阅，迟到消息与错误不再触发调用方", async () => {
  let resolve!: (id: string | number) => void;
  const subscribe = vi.fn<AstrBotPluginPageBridge["subscribeSSE"]>(
    () =>
      new Promise((done) => {
        resolve = done;
      }),
  );
  const unsubscribe = vi.fn();
  window.AstrBotPluginPage = {
    ready: async () => ({}),
    apiGet: async () => null,
    apiPost: async () => null,
    subscribeSSE: subscribe,
    unsubscribeSSE: unsubscribe,
  };
  const onMessage = vi.fn(),
    onError = vi.fn();
  const cleanup = subscribeSSE({ onMessage, onError });
  cleanup?.();
  cleanup?.();
  resolve("late-subscription");
  await Promise.resolve();
  expect(unsubscribe).toHaveBeenCalledTimes(1);
  expect(unsubscribe).toHaveBeenCalledWith("late-subscription");
  subscribe.mock.lastCall![1].onMessage({ parsed: { event: "log_entry" } });
  subscribe.mock.lastCall![1].onError?.();
  expect(onMessage).not.toHaveBeenCalled();
  expect(onError).not.toHaveBeenCalled();
});

it("正常订阅转发解析事件与错误，清理最多一次，编号零也可注销", async () => {
  const subscribe = vi.fn<AstrBotPluginPageBridge["subscribeSSE"]>().mockResolvedValue(0);
  const unsubscribe = vi.fn();
  window.AstrBotPluginPage = {
    ready: async () => ({}),
    apiGet: async () => null,
    apiPost: async () => null,
    subscribeSSE: subscribe,
    unsubscribeSSE: unsubscribe,
  };
  const onMessage = vi.fn(),
    onError = vi.fn();
  const cleanup = subscribeSSE({ onMessage, onError });
  await Promise.resolve();
  subscribe.mock.lastCall![1].onMessage({ parsed: { event: "log_entry" } });
  subscribe.mock.lastCall![1].onError?.();
  expect(onMessage).toHaveBeenCalledWith({ event: "log_entry" });
  expect(onError).toHaveBeenCalledTimes(1);
  cleanup?.();
  cleanup?.();
  expect(unsubscribe).toHaveBeenCalledTimes(1);
  expect(unsubscribe).toHaveBeenCalledWith(0);
});

it("宿主拒绝订阅时通过错误回调报告，不留下未处理的 Promise", async () => {
  window.AstrBotPluginPage = {
    ready: async () => ({}),
    apiGet: async () => null,
    apiPost: async () => null,
    subscribeSSE: vi.fn().mockRejectedValue(new Error("订阅失败")),
    unsubscribeSSE: vi.fn(),
  };
  const onError = vi.fn();
  const cleanup = subscribeSSE({ onMessage: vi.fn(), onError });
  await Promise.resolve();
  await Promise.resolve();
  expect(onError).toHaveBeenCalledTimes(1);
  cleanup?.();
});
