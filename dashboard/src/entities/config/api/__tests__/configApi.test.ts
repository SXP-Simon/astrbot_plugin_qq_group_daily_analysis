import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiGet, apiPost } from "../../../../shared/api/bridge";
import { fetchPluginConfig, savePluginConfig, testTemplateCdn } from "../configApi";

vi.mock("../../../../shared/api/bridge", async (importOriginal) => ({
  ...await importOriginal<typeof import("../../../../shared/api/bridge")>(),
  apiGet: vi.fn(), apiPost: vi.fn(),
}));

beforeEach(() => vi.clearAllMocks());

describe("配置 API 边界", () => {
  it("支持宿主双层信封，保留未知配置分组", async () => {
    const payload = { config: { data: { values: [1, ""] } }, schema: {} };
    vi.mocked(apiGet).mockResolvedValue({ status: "ok", data: { status: "ok", data: payload } });
    expect(await fetchPluginConfig()).toEqual(payload);
  });
  it("拒绝损坏响应", async () => {
    vi.mocked(apiGet).mockResolvedValue({ status: "ok", data: { config: {} } });
    await expect(fetchPluginConfig()).rejects.toThrow("配置响应结构无效");
  });
  it("保存与检测在网络调用前拒绝错误格式", async () => {
    const result = await savePluginConfig({ t2i_rendering: { t2i_rendering_strategies: [{ cdn_base_url: "bad" }] } });
    expect(result.success).toBe(false);
    await expect(testTemplateCdn("bad")).rejects.toThrow();
    expect(apiPost).not.toHaveBeenCalled();
  });
  it("保存规范化地址并保留未知字段", async () => {
    vi.mocked(apiPost).mockResolvedValue({ status: "ok", message: "保存成功" });
    const config = { t2i_rendering: { t2i_rendering_strategies: [{ cdn_base_url: " https://example.com/ " }], extra: [1] }, future: { value: null } };
    expect((await savePluginConfig(config)).success).toBe(true);
    expect(apiPost).toHaveBeenCalledWith("config", { config: expect.objectContaining({ future: config.future, t2i_rendering: expect.objectContaining({ extra: [1], t2i_rendering_strategies: [expect.objectContaining({ cdn_base_url: "https://example.com" })] }) }) });
  });
  it("内层保存错误不能被外层 ok 掩盖", async () => {
    vi.mocked(apiPost).mockResolvedValue({ status: "ok", data: { status: "error", message: "CDN 地址无效" } });
    expect(await savePluginConfig({})).toEqual({ success: false, message: "CDN 地址无效" });
  });
  it.each([null, {}, { data: {} }])("不能将未知响应当作成功：%j", async (response) => {
    vi.mocked(apiPost).mockResolvedValue(response);
    expect((await savePluginConfig({})).success).toBe(false);
  });
});


it("读取和保存时传递配置版本，并接收新的版本", async () => {
  const revision = "a".repeat(64);
  const nextRevision = "b".repeat(64);
  vi.mocked(apiGet).mockResolvedValue({ status: "ok", data: { config: {}, schema: {}, revision } });
  expect((await fetchPluginConfig()).revision).toBe(revision);
  vi.mocked(apiPost).mockResolvedValue({ status: "ok", data: { status: "ok", revision: nextRevision } });
  expect(await savePluginConfig({}, revision)).toEqual({ success: true, message: "配置已成功保存并持久化生效", revision: nextRevision });
  expect(apiPost).toHaveBeenCalledWith("config", { config: {}, revision });
});

it("旧版本冲突保留后端提示，损坏版本不能通过响应校验", async () => {
  vi.mocked(apiPost).mockResolvedValue({ status: "error", message: "配置已被其他页面修改，请重新读取后再保存。当前改动尚未保存。" });
  expect((await savePluginConfig({}, "a".repeat(64))).success).toBe(false);
  vi.mocked(apiGet).mockResolvedValue({ status: "ok", data: { config: {}, schema: {}, revision: 123 } });
  await expect(fetchPluginConfig()).rejects.toThrow("配置响应结构无效");
});
