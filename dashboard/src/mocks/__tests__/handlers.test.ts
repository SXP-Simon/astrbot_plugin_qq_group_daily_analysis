import { describe, it, expect } from "vitest";
import { mockHandlers } from "../handlers";
import { createMswHandlerDefinitions } from "../mswHandlers";
import { mockTraces } from "../data/traces";

describe("Mock Handlers Router & Dispatcher", () => {
  it("should return metrics summary data with valid KPI fields", () => {
    const res = mockHandlers["GET metrics/summary"]();
    expect(res.status).toBe("ok");
    expect(res.data).toBeDefined();
    expect(res.data.total_traces).toBeGreaterThan(0);
    expect(res.data.success_rate).toBeGreaterThan(0);
  });

  it("should filter trace list by status", () => {
    const allRes = mockHandlers["GET traces"]();
    expect(allRes.data.items.length).toBeGreaterThan(0);

    const filteredRes = mockHandlers["GET traces"]({ status: "failed" });
    expect(filteredRes.data.items.every((t) => t.status === "failed")).toBe(true);
  });

  it("should handle parameterized trace details", () => {
    const res = mockHandlers["GET traces/:traceId"](undefined, { traceId: "trace-20260926-001" });
    expect(res.status).toBe("ok");
    expect(res.data.trace_id).toBe("trace-20260926-001");
    expect(Array.isArray(res.data.spans)).toBe(true);
  });

  it("should provide 3 comprehensive Golden Mocks with different business scenarios", () => {
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

  it("should handle trigger task action", () => {
    const res = mockHandlers["POST tasks/trigger"]();
    expect(res.status).toBe("ok");
    expect(res.data.trace_id).toBeDefined();
  });

  it("should handle report templates query", () => {
    const res = mockHandlers["GET reports/templates"]();
    expect(res.status).toBe("ok");
    expect(Array.isArray(res.data)).toBe(true);
    expect(res.data.some((t) => t.id === "scrapbook")).toBe(true);
  });

  it("should generate MSW compatible handler definitions", () => {
    const defs = createMswHandlerDefinitions("/api/plugins/astrbot_plugin_qq_group_daily_analysis");
    expect(defs.length).toBeGreaterThan(15);
    const getTracesDef = defs.find((d) => d.method === "GET" && d.path === "traces");
    expect(getTracesDef).toBeDefined();
    expect(getTracesDef?.urlPattern).toBe("/api/plugins/astrbot_plugin_qq_group_daily_analysis/traces");

    const resolved = getTracesDef?.resolver({ query: { status: "succeeded" } });
    expect(resolved?.status).toBe("ok");
  });
});
