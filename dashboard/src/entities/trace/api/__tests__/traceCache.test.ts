import { beforeEach, expect, it, vi } from "vitest";
import { apiGet } from "../../../../shared/api/bridge";
import { fetchTraceDetail, invalidateTraceCache } from "../traceApi";
import type { TraceRecord } from "../../model/types";

vi.mock("../../../../shared/api/bridge", () => ({
  apiGet: vi.fn(),
  apiPost: vi.fn(),
  extractData: (value: unknown) => value,
}));
const trace: TraceRecord = {
  trace_id: "example",
  group_id: "group",
  group_name: "示例",
  platform: "satori",
  trigger_type: "manual",
  status: "succeeded",
  started_at: 1,
};
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}
beforeEach(() => {
  vi.resetAllMocks();
  invalidateTraceCache();
});

it("终态缓存命中，手动强制刷新读取最新内容", async () => {
  vi.mocked(apiGet)
    .mockResolvedValueOnce(trace)
    .mockResolvedValueOnce({ ...trace, total_tokens: 9 });
  await fetchTraceDetail("example");
  expect(await fetchTraceDetail("example")).toEqual(trace);
  expect(apiGet).toHaveBeenCalledTimes(1);
  await fetchTraceDetail("example", true);
  expect((await fetchTraceDetail("example"))?.total_tokens).toBe(9);
  expect(apiGet).toHaveBeenCalledTimes(2);
});

it("待处理记录和已清理记录不留在终态缓存中", async () => {
  vi.mocked(apiGet)
    .mockResolvedValueOnce(trace)
    .mockResolvedValueOnce(null)
    .mockResolvedValueOnce({ ...trace, status: "pending" })
    .mockResolvedValueOnce(trace);
  await fetchTraceDetail("example");
  expect(await fetchTraceDetail("example", true)).toBeNull();
  expect((await fetchTraceDetail("example"))?.status).toBe("pending");
  expect((await fetchTraceDetail("example"))?.status).toBe("succeeded");
  expect(apiGet).toHaveBeenCalledTimes(4);
});

it("缓存达到上限时淘汰最久未访问的记录，保留刚查看过的任务", async () => {
  vi.mocked(apiGet).mockResolvedValue(trace);
  for (let index = 0; index < 100; index++) await fetchTraceDetail(`example-${index}`);
  await fetchTraceDetail("example-0");
  await fetchTraceDetail("example-100");
  await fetchTraceDetail("example-0");
  expect(apiGet).toHaveBeenCalledTimes(101);
  await fetchTraceDetail("example-1");
  expect(apiGet).toHaveBeenCalledTimes(102);
});

it("新终态先返回后，旧运行中响应不能清除新缓存", async () => {
  const old = deferred<TraceRecord>();
  vi.mocked(apiGet).mockReturnValueOnce(old.promise).mockResolvedValueOnce(trace);
  const pending = fetchTraceDetail("example", true);
  await fetchTraceDetail("example", true);
  old.resolve({ ...trace, status: "running" });
  await pending;
  expect(await fetchTraceDetail("example")).toEqual(trace);
  expect(apiGet).toHaveBeenCalledTimes(2);
});

it("SSE 失效后旧响应不会重新填入缓存", async () => {
  const old = deferred<TraceRecord>();
  vi.mocked(apiGet)
    .mockReturnValueOnce(old.promise)
    .mockResolvedValueOnce({ ...trace, total_tokens: 11 });
  const pending = fetchTraceDetail("example");
  invalidateTraceCache("example");
  old.resolve(trace);
  await pending;
  expect((await fetchTraceDetail("example"))?.total_tokens).toBe(11);
  expect(apiGet).toHaveBeenCalledTimes(2);
});

it("全量失效和请求失败后仍能重新获取，运行中记录不缓存", async () => {
  const old = deferred<TraceRecord>();
  vi.mocked(apiGet).mockReturnValueOnce(old.promise).mockRejectedValueOnce(new Error("离线"));
  const pending = fetchTraceDetail("example");
  invalidateTraceCache();
  old.resolve(trace);
  await pending;
  await expect(fetchTraceDetail("example")).rejects.toThrow("离线");
  vi.mocked(apiGet).mockResolvedValue({ ...trace, status: "running" });
  await fetchTraceDetail("example");
  await fetchTraceDetail("example");
  expect(apiGet).toHaveBeenCalledTimes(4);
});
