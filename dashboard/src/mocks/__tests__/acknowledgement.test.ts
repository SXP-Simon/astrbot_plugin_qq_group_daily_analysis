import { expect, it } from "vitest";
import { devApiPost, devApiGet } from "@/shared/api/devBridge";
import { mockTraces } from "@/mocks/data/traces";

it("Mock 通过正式通信路径保存、查询和撤销知晓，保留任务结果", async () => {
  const trace = mockTraces.find((item) => item.status === "failed")!;
  const previous = trace.acknowledged_at;
  try {
    const result = await devApiPost(`traces/${trace.trace_id}/acknowledgement`, {
      acknowledged: true,
    });
    expect(result?.status).toBe("ok");
    expect(trace.acknowledged_at).toBeGreaterThan(0);
    const detail = await devApiGet(`traces/${trace.trace_id}`);
    expect(detail?.data).toMatchObject({
      status: "failed",
      acknowledged_at: trace.acknowledged_at,
    });
    await devApiPost(`traces/${trace.trace_id}/acknowledgement`, { acknowledged: false });
    expect(trace.acknowledged_at).toBeNull();
    expect(
      (await devApiPost("traces/missing/acknowledgement", { acknowledged: true }))?.status,
    ).toBe("error");
    expect(
      (await devApiPost(`traces/${trace.trace_id}/acknowledgement`, { acknowledged: "yes" }))
        ?.status,
    ).toBe("error");
  } finally {
    trace.acknowledged_at = previous;
  }
});
