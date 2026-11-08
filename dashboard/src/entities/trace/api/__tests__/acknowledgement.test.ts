import { beforeEach, expect, it, vi } from "vitest";
import { apiGet, apiPost } from "../../../../shared/api/bridge";
import { acknowledgeTrace, fetchTraceDetail, invalidateTraceCache } from "../traceApi";

vi.mock("../../../../shared/api/bridge", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../../shared/api/bridge")>()),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));
beforeEach(() => {
  vi.resetAllMocks();
  invalidateTraceCache();
});
it("保存与撤销知晓后清理终态缓存，下次详情重新读取", async () => {
  vi.mocked(apiGet).mockResolvedValue({
    status: "ok",
    data: { trace_id: "a/b", status: "failed" },
  });
  await fetchTraceDetail("a/b");
  vi.mocked(apiPost).mockResolvedValue({
    status: "ok",
    data: { trace_id: "a/b", acknowledged_at: 123 },
  });
  expect(await acknowledgeTrace("a/b", true)).toEqual({ trace_id: "a/b", acknowledged_at: 123 });
  expect(apiPost).toHaveBeenCalledWith("traces/a%2Fb/acknowledgement", { acknowledged: true });
  await fetchTraceDetail("a/b");
  expect(apiGet).toHaveBeenCalledTimes(2);
  vi.mocked(apiPost).mockResolvedValue({
    status: "ok",
    data: { trace_id: "a/b", acknowledged_at: null },
  });
  expect((await acknowledgeTrace("a/b", false)).acknowledged_at).toBeNull();
});
it.each([
  { trace_id: "wrong", acknowledged_at: 123 },
  { trace_id: "example", acknowledged_at: null },
  { trace_id: "example", acknowledged_at: "123" },
  { trace_id: "example", acknowledged_at: 0 },
])("拒绝无效或串任务回执 %j", async (data) => {
  vi.mocked(apiPost).mockResolvedValue({ status: "ok", data });
  await expect(acknowledgeTrace("example", true)).rejects.toThrow("知晓状态未能确认");
});
it("保存失败不报告成功", async () => {
  vi.mocked(apiPost).mockResolvedValue({ status: "error", message: "保存失败" });
  await expect(acknowledgeTrace("example", true)).rejects.toThrow();
});
