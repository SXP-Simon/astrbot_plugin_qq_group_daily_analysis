import { afterEach, describe, expect, it, vi } from "vitest";
import { apiGet } from "../../../shared/api/bridge";
import { fetchManagedRecord } from "./managedRecordsApi";

vi.mock("../../../shared/api/bridge", async importOriginal => ({
  ...await importOriginal<typeof import("../../../shared/api/bridge")>(), apiGet: vi.fn(),
}));
afterEach(() => vi.clearAllMocks());

describe("业务记录响应信封", () => {
  const record = { locator: { kind: "history", key: "analysis_123_2026-11-03_12-00" }, data: { summary: {}, analysis: { topics: [] } }, revision: "current" };
  it.each([record, { status: "ok", data: record }])("不会剥离记录本身的 data 产物", async envelope => {
    vi.mocked(apiGet).mockResolvedValue({ status: "ok", data: envelope });
    expect(await fetchManagedRecord(record.locator)).toEqual(record);
  });
  it("保留记录已过期的错误原因", async () => {
    vi.mocked(apiGet).mockResolvedValue({ status: "error", message: "快照已过期" });
    await expect(fetchManagedRecord({ kind: "checkpoint" })).rejects.toThrow("快照已过期");
  });
  it("业务产物中的记录字段不能替代外层记录的标识与版本", async () => {
    const outer = { ...record, data: { locator: { kind: "avatar", key: "inner" }, revision: "inner", data: {} } };
    vi.mocked(apiGet).mockResolvedValue(outer);
    expect(await fetchManagedRecord(record.locator)).toEqual(outer);
  });
});
