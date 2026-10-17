import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { apiGet, apiPost, extractData, fetchContext, subscribeSSE, type AstrBotPluginPageBridge } from "../bridge";

describe("API 通信网桥 (Shared API Bridge)", () => {
  beforeEach(() => {
    delete (window as { AstrBotPluginPage?: unknown }).AstrBotPluginPage;
  });

  it("当 window 上不存在 AstrBotPluginPage 时，应当平滑降级至本地 devBridge", async () => {
    const ctx = await fetchContext();
    expect(ctx).toBeDefined();
    expect(ctx.pluginName).toBe("astrbot_plugin_qq_group_daily_analysis");
  });

  it("在开发环境下能够通过 devBridge 正确获取大盘指标概览", async () => {
    const res = await apiGet("metrics/summary");
    expect(res).toBeDefined();
    expect(res?.status).toBe("ok");
    const data = extractData<{ total_traces: number }>(res);
    expect(data?.total_traces).toBeGreaterThan(0);
  });

  it("在开发环境下能够通过 devBridge 模拟 POST 提交分析任务", async () => {
    const res = await apiPost("tasks/trigger", { group_id: "123456789" });
    expect(res).toBeDefined();
    expect(res?.status).toBe("ok");
  });

  it("能够通过 devBridge 正确获取活跃任务列表", async () => {
    const res = await apiGet("tasks/active");
    expect(res).toBeDefined();
    const data = extractData<unknown[]>(res);
    expect(Array.isArray(data)).toBe(true);
  });

  it("extractData 工具函数能够正确解包多层嵌套或扁平的响应结构", () => {
    // 1. 三层/双层包装解包
    expect(extractData({ data: { data: { foo: "bar" } } })).toEqual({ foo: "bar" });
    // 2. 单层 data 包装
    expect(extractData({ data: [1, 2, 3] })).toEqual([1, 2, 3]);
    // 3. 扁平对象
    expect(extractData({ result: "direct" })).toEqual({ result: "direct" });
    // 4. 空值与容错安全处理
    expect(extractData(null)).toBeNull();
    expect(extractData(undefined)).toBeNull();
  });

  it("支持对本地 Mock SSE 事件流进行订阅与注销", () => {
    let receivedCount = 0;
    const unsubscribe = subscribeSSE({
      onMessage: () => {
        receivedCount += 1;
      },
    });
    expect(typeof unsubscribe).toBe("function");
    expect(receivedCount).toBe(0);
    if (unsubscribe) {
      unsubscribe();
    }
  });
});

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (reason: Error) => void;
  const promise = new Promise<T>((done, fail) => { resolve = done; reject = fail; });
  return { promise, resolve, reject };
}

function installHost(pending: Promise<string | number> = Promise.resolve("shared")) {
  const subscribe = vi.fn<AstrBotPluginPageBridge["subscribeSSE"]>().mockReturnValue(pending);
  const unsubscribe = vi.fn();
  window.AstrBotPluginPage = {
    ready: async () => ({}),
    apiGet: async () => null,
    apiPost: async () => null,
    subscribeSSE: subscribe,
    unsubscribeSSE: unsubscribe,
  };
  return { subscribe, unsubscribe };
}

describe("同页宿主 SSE 连接复用", () => {
  afterEach(() => { delete window.AstrBotPluginPage; });

  it("总览和日志共用连接，独立接收消息和错误，最后一个监听者退出才释放", async () => {
    const host = installHost();
    const overview = { onMessage: vi.fn(), onError: vi.fn() };
    const logs = { onMessage: vi.fn(), onError: vi.fn() };
    const stopOverview = subscribeSSE(overview)!;
    const stopLogs = subscribeSSE(logs)!;
    await Promise.resolve();
    expect(host.subscribe).toHaveBeenCalledTimes(1);
    const events = host.subscribe.mock.calls[0][1];
    const payload = { event: "task_finished" };
    events.onMessage({ parsed: payload, raw: "不应使用" });
    events.onError?.();
    expect(overview.onMessage).toHaveBeenCalledWith(payload);
    expect(logs.onMessage).toHaveBeenCalledWith(payload);
    expect(overview.onError).toHaveBeenCalledTimes(1);
    expect(logs.onError).toHaveBeenCalledTimes(1);
    stopOverview();
    expect(host.unsubscribe).not.toHaveBeenCalled();
    events.onMessage({ raw: "原始消息" });
    expect(overview.onMessage).toHaveBeenCalledTimes(1);
    expect(logs.onMessage).toHaveBeenLastCalledWith("原始消息");
    stopLogs();
    stopLogs();
    expect(host.unsubscribe.mock.calls).toEqual([["shared"]]);
    events.onMessage({ parsed: "连接关闭后的迟到消息" });
    expect(logs.onMessage).toHaveBeenCalledTimes(2);
  });

  it("卸载早于订阅 ID 返回时，仍取消迟到连接并忽略后续事件", async () => {
    const pending = deferred<string | number>();
    const host = installHost(pending.promise);
    const listener = { onMessage: vi.fn(), onError: vi.fn() };
    const stop = subscribeSSE(listener)!;
    stop();
    expect(host.unsubscribe).not.toHaveBeenCalled();
    pending.resolve(0);
    await Promise.resolve();
    expect(host.unsubscribe.mock.calls).toEqual([[0]]);
    host.subscribe.mock.calls[0][1].onMessage({ parsed: "迟到" });
    host.subscribe.mock.calls[0][1].onError?.();
    expect(listener.onMessage).not.toHaveBeenCalled();
    expect(listener.onError).not.toHaveBeenCalled();
  });

  it("快速卸载再挂载时，旧订阅迟到不会关闭新连接", async () => {
    const old = deferred<string | number>();
    const recent = deferred<string | number>();
    const host = installHost(old.promise);
    host.subscribe.mockReturnValueOnce(old.promise).mockReturnValueOnce(recent.promise);
    const oldListener = vi.fn();
    const newListener = vi.fn();
    const stopOld = subscribeSSE({ onMessage: oldListener })!;
    stopOld();
    const stopNew = subscribeSSE({ onMessage: newListener })!;
    expect(host.subscribe).toHaveBeenCalledTimes(2);
    recent.resolve("new");
    old.resolve("old");
    await Promise.resolve();
    expect(host.unsubscribe.mock.calls).toEqual([["old"]]);
    host.subscribe.mock.calls[0][1].onMessage({ parsed: "旧消息" });
    host.subscribe.mock.calls[1][1].onMessage({ parsed: "新消息" });
    expect(oldListener).not.toHaveBeenCalled();
    expect(newListener.mock.calls).toEqual([["新消息"]]);
    stopOld();
    expect(host.unsubscribe).toHaveBeenCalledTimes(1);
    stopNew();
    expect(host.unsubscribe).toHaveBeenLastCalledWith("new");
  });

  it("日志切换筛选条件不会重开仍由总览使用的连接", async () => {
    const host = installHost();
    const overview = vi.fn();
    const oldFilter = vi.fn();
    const newFilter = vi.fn();
    const stopOverview = subscribeSSE({ onMessage: overview })!;
    const stopOldFilter = subscribeSSE({ onMessage: oldFilter })!;
    stopOldFilter();
    const stopNewFilter = subscribeSSE({ onMessage: newFilter })!;
    await Promise.resolve();
    host.subscribe.mock.calls[0][1].onMessage({ parsed: "新日志" });
    expect(host.subscribe).toHaveBeenCalledTimes(1);
    expect(oldFilter).not.toHaveBeenCalled();
    expect(overview.mock.calls).toEqual([["新日志"]]);
    expect(newFilter.mock.calls).toEqual([["新日志"]]);
    stopOverview();
    stopNewFilter();
  });

  it("一个视图处理消息或错误失败时，其他视图仍能收到通知", async () => {
    const host = installHost();
    const failed = () => { throw new Error("视图异常"); };
    const stopBroken = subscribeSSE({ onMessage: failed, onError: failed })!;
    const healthy = { onMessage: vi.fn(), onError: vi.fn() };
    const stopHealthy = subscribeSSE(healthy)!;
    await Promise.resolve();
    const events = host.subscribe.mock.calls[0][1];
    expect(() => events.onMessage({ parsed: 1 })).not.toThrow();
    expect(() => events.onError?.()).not.toThrow();
    expect(healthy.onMessage.mock.calls).toEqual([[1]]);
    expect(healthy.onError).toHaveBeenCalledTimes(1);
    stopBroken();
    stopHealthy();
  });

  it("订阅创建失败通知各监听者，后续订阅可以重新建立连接", async () => {
    const pending = deferred<string | number>();
    const host = installHost(pending.promise);
    const first = { onMessage: vi.fn(), onError: vi.fn() };
    const second = { onMessage: vi.fn(), onError: vi.fn() };
    const stopFirst = subscribeSSE(first)!;
    const stopSecond = subscribeSSE(second)!;
    pending.reject(new Error("宿主无法建立订阅"));
    await Promise.resolve();
    await Promise.resolve();
    expect(first.onError).toHaveBeenCalledTimes(1);
    expect(second.onError).toHaveBeenCalledTimes(1);
    host.subscribe.mockResolvedValueOnce("retried");
    const retried = vi.fn();
    const stopRetry = subscribeSSE({ onMessage: retried })!;
    await Promise.resolve();
    expect(host.subscribe).toHaveBeenCalledTimes(2);
    stopFirst();
    stopSecond();
    expect(host.unsubscribe).not.toHaveBeenCalled();
    host.subscribe.mock.calls[1][1].onMessage({ parsed: "恢复" });
    expect(retried.mock.calls).toEqual([["恢复"]]);
    stopRetry();
    expect(host.unsubscribe.mock.calls).toEqual([["retried"]]);
  });

  it("同一回调重复订阅仍能分别取消", async () => {
    const host = installHost();
    const listener = { onMessage: vi.fn() };
    const first = subscribeSSE(listener)!;
    const second = subscribeSSE(listener)!;
    await Promise.resolve();
    host.subscribe.mock.calls[0][1].onMessage({ parsed: "两次订阅" });
    expect(listener.onMessage).toHaveBeenCalledTimes(2);
    first();
    expect(host.unsubscribe).not.toHaveBeenCalled();
    host.subscribe.mock.calls[0][1].onMessage({ parsed: "剩余订阅" });
    expect(listener.onMessage).toHaveBeenCalledTimes(3);
    second();
    expect(host.unsubscribe).toHaveBeenCalledTimes(1);
  });
});
