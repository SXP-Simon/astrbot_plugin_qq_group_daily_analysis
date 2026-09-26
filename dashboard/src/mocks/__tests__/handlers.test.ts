import { describe, it, expect } from "vitest";
import { mockHandlers } from "../handlers";
import { createMswHandlerDefinitions } from "../mswHandlers";
import { mockTraces } from "../data/traces";

describe("Mock 路由分发器与数据源 (Mock Handlers & Dispatcher)", () => {
  it("应当返回包含核心 KPI 字段的指标大盘概览数据", () => {
    const res = mockHandlers["GET metrics/summary"]();
    expect(res.status).toBe("ok");
    expect(res.data).toBeDefined();
    expect(res.data.total_traces).toBeGreaterThan(0);
    expect(res.data.success_rate).toBeGreaterThan(0);
  });

  it("应当支持按任务状态对链路列表进行过滤筛选", () => {
    const allRes = mockHandlers["GET traces"]();
    expect(allRes.data.items.length).toBeGreaterThan(0);

    const filteredRes = mockHandlers["GET traces"]({ status: "failed" });
    expect(filteredRes.data.items.every((t) => t.status === "failed")).toBe(true);
  });

  it("应当支持带动态参数的链路详情查询", () => {
    const res = mockHandlers["GET traces/:traceId"](undefined, { traceId: "trace-20260926-001" });
    expect(res.status).toBe("ok");
    expect(res.data.trace_id).toBe("trace-20260926-001");
    expect(Array.isArray(res.data.spans)).toBe(true);
  });

  it("提供 3 套覆盖完整业务场景的高保真 Golden Mocks (正常分析/超时中断/多模态漫画)", () => {
    expect(mockTraces.length).toBeGreaterThanOrEqual(3);
    const successTrace = mockTraces.find((t) => t.status === "succeeded" && !t.extra?.comic_enabled);
    const failedTrace = mockTraces.find((t) => t.status === "failed");
    const comicTrace = mockTraces.find((t) => t.extra?.comic_enabled);

    expect(successTrace).toBeDefined();
    expect(failedTrace).toBeDefined();
    expect(comicTrace).toBeDefined();
    expect(failedTrace?.error_message).toContain("Connection timeout");
    expect(comicTrace?.spans?.some((s) => s.stage_name === "comic_generation")).toBe(true);
  });

  it("应当支持手动触发分析任务并返回排队 Trace ID", () => {
    const res = mockHandlers["POST tasks/trigger"]();
    expect(res.status).toBe("ok");
    expect(res.data.trace_id).toBeDefined();
  });

  it("应当返回可用的海报视觉主题模板列表", () => {
    const res = mockHandlers["GET reports/templates"]();
    expect(res.status).toBe("ok");
    expect(Array.isArray(res.data)).toBe(true);
    expect(res.data.some((t) => t.id === "scrapbook")).toBe(true);
  });

  it("应当正确生成符合 MSW 标准规范的 Handler 定义列表", () => {
    const defs = createMswHandlerDefinitions("/api/plugins/astrbot_plugin_qq_group_daily_analysis");
    expect(defs.length).toBeGreaterThan(15);
    const getTracesDef = defs.find((d) => d.method === "GET" && d.path === "traces");
    expect(getTracesDef).toBeDefined();
    expect(getTracesDef?.urlPattern).toBe("/api/plugins/astrbot_plugin_qq_group_daily_analysis/traces");

    const resolved = getTracesDef?.resolver({ query: { status: "succeeded" } });
    expect(resolved?.status).toBe("ok");
  });
});
