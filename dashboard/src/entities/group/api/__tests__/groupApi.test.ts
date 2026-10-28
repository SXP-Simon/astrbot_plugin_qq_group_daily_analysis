import { beforeEach, expect, it, vi } from "vitest";
import { apiGet } from "../../../../shared/api/bridge";
import { mockHandlers } from "../../../../mocks/handlers";
import { fetchDistinctGroups, fetchGroupSessions, invalidateGroupsCache } from "../groupApi";

vi.mock("../../../../shared/api/bridge", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../../../shared/api/bridge")>(), apiGet: vi.fn(),
}));

beforeEach(() => { vi.resetAllMocks(); invalidateGroupsCache(); });

it("读取真实 mock 数据后保留群名和平台，缓存只在校验通过后生效", async () => {
  vi.mocked(apiGet).mockResolvedValue(mockHandlers["GET groups"]());
  const groups = await fetchDistinctGroups();
  expect(groups[0]).toEqual({ group_id: "123456789", group_name: "技术交流与闲聊吹水群", platform: "aiocqhttp_main" });
  expect(await fetchDistinctGroups()).toEqual(groups);
  expect(apiGet).toHaveBeenCalledTimes(1);
});

it.each([["123"], [{ group_id: "123" }], [{ group_id: "123", group_name: "群", platform: 1 }], null])("拒绝错误群列表 %j，不缓存异常数据", async (data) => {
  vi.mocked(apiGet).mockResolvedValueOnce({ status: "ok", data }).mockResolvedValueOnce(mockHandlers["GET groups"]());
  await expect(fetchDistinctGroups()).rejects.toThrow("群列表格式不正确");
  expect((await fetchDistinctGroups()).length).toBeGreaterThan(0);
  expect(apiGet).toHaveBeenCalledTimes(2);
});

it("兼容宿主双层信封和没有历史记录的空列表", async () => {
  vi.mocked(apiGet).mockResolvedValue({ status: "ok", data: { status: "ok", data: [] } });
  expect(await fetchDistinctGroups()).toEqual([]);
});


it("测试渲染读取独立会话列表，不使用按群号去重的缓存", async () => {
  vi.mocked(apiGet).mockResolvedValueOnce(mockHandlers["GET groups"]()).mockResolvedValueOnce({ status: "ok", data: [
    { group_id: "1", group_name: "群", platform: "onebot_1" },
    { group_id: "1", group_name: "群", platform: "onebot_2" },
  ] });
  await fetchDistinctGroups();
  expect(await fetchGroupSessions()).toHaveLength(2);
  expect(apiGet).toHaveBeenLastCalledWith("groups", { by_session: true });
});
