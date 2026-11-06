import { afterEach, expect, it, vi } from "vitest";
import { apiGet } from "../../../shared/api/bridge";
import { fetchCheckpointDetail } from "./pluginDataApi";

vi.mock("../../../shared/api/bridge", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../../../shared/api/bridge")>()),
  apiGet: vi.fn(),
}));
afterEach(() => vi.clearAllMocks());

it.each([0, 1, 2])("快照经过 %i 层桥接解包后保留元数据和完整产物", async (layers) => {
  const detail = {
    group_id: "GROUP",
    date_str: "2026-11-04",
    stage_name: "LLM_ANALYSIS",
    trace_id: "TRACE",
    data: { stage_name: "业务产物中的同名字段", data: { topics: [] } },
  };
  let response: unknown = detail;
  for (let depth = 0; depth < layers; depth += 1) response = { status: "ok", data: response };
  vi.mocked(apiGet).mockResolvedValue(response as Awaited<ReturnType<typeof apiGet>>);
  expect(await fetchCheckpointDetail("GROUP", "2026-11-04", "LLM_ANALYSIS", "TRACE")).toEqual(
    detail,
  );
});

it("保留旧版 detail 包装并拒绝缺少快照元数据的响应", async () => {
  const detail = {
    group_id: "GROUP",
    date_str: "2026-11-04",
    stage_name: "LLM_ANALYSIS",
    data: {},
  };
  vi.mocked(apiGet).mockResolvedValue({ status: "ok", detail, data: detail });
  expect(await fetchCheckpointDetail("GROUP", "2026-11-04", "LLM_ANALYSIS")).toEqual(detail);
  vi.mocked(apiGet).mockResolvedValue({ status: "ok", data: { data: {} } });
  await expect(fetchCheckpointDetail("GROUP", "2026-11-04", "LLM_ANALYSIS")).rejects.toThrow(
    "快照详情",
  );
});
