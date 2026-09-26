import { describe, it, expect, beforeEach } from "vitest";
import { apiGet, apiPost, extractData, fetchContext, subscribeSSE } from "../bridge";

describe("Shared API Bridge", () => {
  beforeEach(() => {
    delete (window as { AstrBotPluginPage?: unknown }).AstrBotPluginPage;
  });

  it("should gracefully fallback to devBridge when AstrBotPluginPage is not on window", async () => {
    const ctx = await fetchContext();
    expect(ctx).toBeDefined();
    expect(ctx.pluginName).toBe("astrbot_plugin_qq_group_daily_analysis");
  });

  it("should fetch metrics summary via dev fallback in dev mode", async () => {
    const res = await apiGet("metrics/summary");
    expect(res).toBeDefined();
    expect(res?.status).toBe("ok");
    const data = extractData<{ total_traces: number }>(res);
    expect(data?.total_traces).toBeGreaterThan(0);
  });

  it("should post data via dev fallback in dev mode", async () => {
    const res = await apiPost("tasks/trigger", { group_id: "123456789" });
    expect(res).toBeDefined();
    expect(res?.status).toBe("ok");
  });

  it("should fetch active tasks via dev fallback", async () => {
    const res = await apiGet("tasks/active");
    expect(res).toBeDefined();
    const data = extractData<unknown[]>(res);
    expect(Array.isArray(data)).toBe(true);
  });

  it("should correctly unpack nested responses in extractData", () => {
    // 1. Triple/double wrapped
    expect(extractData({ data: { data: { foo: "bar" } } })).toEqual({ foo: "bar" });
    // 2. Single data wrap
    expect(extractData({ data: [1, 2, 3] })).toEqual([1, 2, 3]);
    // 3. Flat object
    expect(extractData({ result: "direct" })).toEqual({ result: "direct" });
    // 4. Nullish handling
    expect(extractData(null)).toBeNull();
    expect(extractData(undefined)).toBeNull();
  });

  it("should support subscribing and unsubscribing to mock SSE stream", () => {
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
