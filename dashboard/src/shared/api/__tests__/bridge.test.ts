import { describe, it, expect, beforeEach, vi } from "vitest";
import { apiGet, apiPost, apiUpload, extractData, fetchContext, subscribeSSE } from "../bridge";

describe("API 通信网桥 (Shared API Bridge)", () => {
  beforeEach(() => {
    delete (window as { AstrBotPluginPage?: unknown }).AstrBotPluginPage;
  });

  it("二进制上传使用宿主允许的不带查询参数路径并兼容扁平回执", async () => {
    const upload = vi.fn(async (path: string, file: File) => {
      expect(path).not.toContain("?");
      expect(file.size).toBe(20);
      return { received: 20, total: 20, complete: true };
    });
    window.AstrBotPluginPage = { upload } as unknown as NonNullable<Window["AstrBotPluginPage"]>;
    const file = new File([new Uint8Array(20)], "font.ttf");
    expect(await apiUpload("plugin-data/files/upload/uuid/0", file)).toMatchObject({
      received: 20,
    });
    expect(upload).toHaveBeenCalledWith("plugin-data/files/upload/uuid/0", file);
  });

  it("当 window 上不存在 AstrBotPluginPage 时，应当平滑降级至本地 devBridge", async () => {
    const ctx = await fetchContext();
    expect(ctx).toBeDefined();
    expect(ctx.pluginName).toBe("astrbot_plugin_qq_group_daily_analysis");
    expect(ctx.isDark).toBeUndefined();
  });

  it("在开发环境下能够通过 devBridge 正确获取大盘指标概览", async () => {
    const res = await apiGet("metrics/summary");
    expect(res).toBeDefined();
    expect(res?.status).toBe("ok");
    const data = extractData<{ total_traces: number }>(res);
    expect(data?.total_traces).toBeGreaterThan(0);
  });

  it("在开发环境下能够通过 devBridge 模拟 POST 提交分析任务", async () => {
    const res = await apiPost("tasks/trigger", {
      group_id: "123456789",
      platform: "aiocqhttp_main",
    });
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

  it.each([0, 1, 2])("解包 %i 层响应时保留记录的业务 data 和版本", (layers) => {
    const record = {
      locator: { kind: "history", key: "report" },
      revision: "current",
      data: { data: { topics: [] } },
    };
    let response: unknown = record;
    for (let depth = 0; depth < layers; depth += 1) response = { status: "ok", data: response };
    expect(extractData(response)).toEqual(record);
    const checkpoint = {
      stage_name: "LLM_ANALYSIS",
      status: "error",
      data: { error: "业务失败记录" },
    };
    expect(extractData({ status: "ok", data: checkpoint })).toEqual(checkpoint);
  });

  it.each([
    { status: "error", message: "操作未完成", data: { success: true } },
    { status: "ok", data: { status: "error", message: "操作未完成", data: null } },
    { code: 500, message: "操作未完成", data: {} },
  ])("实际桥接和 Mock 的错误响应均不能被当成成功：%j", async (response) => {
    window.AstrBotPluginPage = {
      ready: async () => ({}),
      apiGet: vi.fn().mockResolvedValue(response),
      apiPost: vi.fn().mockResolvedValue(response),
      subscribeSSE: async () => "unused",
      unsubscribeSSE: () => {},
    };
    await expect(apiGet("test")).rejects.toThrow("操作未完成");
    await expect(apiPost("test")).rejects.toThrow("操作未完成");
  });

  it("未收到桥接响应时明确报错", async () => {
    window.AstrBotPluginPage = {
      ready: async () => ({}),
      apiGet: vi.fn().mockResolvedValue(null),
      apiPost: vi.fn().mockResolvedValue(null),
      subscribeSSE: async () => "unused",
      unsubscribeSSE: () => {},
    };
    await expect(apiGet("test")).rejects.toThrow("未收到");
    await expect(apiPost("test")).rejects.toThrow("未收到");
  });
});

it("文件读取超时会结束等待；迟到响应不改变结果，正常响应清理定时器", async () => {
  vi.useFakeTimers();
  try {
    let complete: (result: { data: string }) => void = () => {};
    const api = vi.fn(
      () =>
        new Promise<{ data: string }>((resolve) => {
          complete = resolve;
        }),
    );
    window.AstrBotPluginPage = { apiGet: api } as unknown as NonNullable<
      Window["AstrBotPluginPage"]
    >;
    const request = apiGet("reports/content", { filename: "large.png" }, 30000);
    const rejected = expect(request).rejects.toThrow("读取超过 30 秒");
    await vi.advanceTimersByTimeAsync(30000);
    await rejected;
    complete({ data: "late" });
    await vi.advanceTimersByTimeAsync(0);
    expect(vi.getTimerCount()).toBe(0);
    api.mockResolvedValueOnce({ data: "ready" });
    expect(await apiGet("reports/content", {}, 30000)).toEqual({ data: "ready" });
    expect(vi.getTimerCount()).toBe(0);
  } finally {
    delete window.AstrBotPluginPage;
    vi.useRealTimers();
  }
});
