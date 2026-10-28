import { beforeEach, expect, it, vi } from "vitest";
import { apiGet } from "../../../../shared/api/bridge";
import { fetchPluginLogs } from "../logApi";

vi.mock("../../../../shared/api/bridge", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../../../shared/api/bridge")>(), apiGet: vi.fn(),
}));

beforeEach(() => vi.resetAllMocks());

it("保留正确的日志分类，兼容宿主双层响应", async () => {
  const data = { items: [], total: 0, available_tags: [{ key: "LLM", label: "大模型调用" }] };
  vi.mocked(apiGet).mockResolvedValue({ status: "ok", data: { status: "ok", data } });
  expect(await fetchPluginLogs()).toEqual(data);
});

it("错误的分类结构不会产生空白选项，也不丢弃日志", async () => {
  const items = [{ id: "one", message: "测试" }];
  vi.mocked(apiGet).mockResolvedValue({ status: "ok", data: { items, total: 1, available_tags: [{ tag: "LLM" }] } });
  expect(await fetchPluginLogs()).toEqual({ items, total: 1, available_tags: [] });
});
