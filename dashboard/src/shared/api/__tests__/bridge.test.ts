import { describe, it, expect, beforeEach } from "vitest";
import { apiGet, apiPost, extractData, fetchContext, subscribeSSE } from "../bridge";

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
