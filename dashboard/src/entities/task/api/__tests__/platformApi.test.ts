import { beforeEach, expect, it, vi } from "vitest";
import { apiGet } from "../../../../shared/api/bridge";
import { fetchConnectedPlatforms } from "../taskApi";
import { mockConnectedPlatforms } from "../../../../mocks/data/tasks";

vi.mock("../../../../shared/api/bridge", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../../../shared/api/bridge")>(), apiGet: vi.fn(),
}));

beforeEach(() => vi.resetAllMocks());

it("读取平台实例的真实字段，支持宿主双层响应", async () => {
  vi.mocked(apiGet).mockResolvedValue({ status: "ok", data: { status: "ok", data: mockConnectedPlatforms } });
  expect(await fetchConnectedPlatforms()).toEqual(mockConnectedPlatforms);
});

it.each([["qq"], [{ id: "qq", label: "QQ" }], null])("拒绝无效平台列表 %j", async (data) => {
  vi.mocked(apiGet).mockResolvedValue({ status: "ok", data });
  await expect(fetchConnectedPlatforms()).rejects.toThrow("平台列表格式不正确");
});
