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
    const result = await savePluginConfig({ t2i_rendering: { t2i_cdn_base_url: "bad" } });
    expect(result.success).toBe(false);
    await expect(testTemplateCdn("bad")).rejects.toThrow();
    expect(apiPost).not.toHaveBeenCalled();
  });
  it("保存规范化地址并保留未知字段", async () => {
    vi.mocked(apiPost).mockResolvedValue({ status: "ok", message: "保存成功" });
    const config = { t2i_rendering: { t2i_cdn_base_url: " https://example.com/ ", extra: [1] }, future: { value: null } };
    expect((await savePluginConfig(config)).success).toBe(true);
    expect(apiPost).toHaveBeenCalledWith("config", { config: { ...config, t2i_rendering: { ...config.t2i_rendering, t2i_cdn_base_url: "https://example.com" } } });
  });
  it("内层保存错误不能被外层 ok 掩盖", async () => {
    vi.mocked(apiPost).mockResolvedValue({ status: "ok", data: { status: "error", message: "CDN 地址无效" } });
    expect(await savePluginConfig({})).toEqual({ success: false, message: "CDN 地址无效" });
  });
  it.each(["宿主已解包", "原始 HTTP 响应", "旧宿主双层信封"])("识别保存回执：%s", async (mode) => {
    const receipt = {
      status: "ok", message: "配置已成功保存并持久化生效",
      config: { prompts: { comic_analysis_prompts: { comic_storyboard_template: "noir_detective" } } },
    };
    const httpResponse = { status: "ok", message: receipt.message, data: receipt };
    // 当前 AstrBot PluginPagePage.vue 会转发 response.data?.data ?? response.data。
    const response = mode === "宿主已解包" ? httpResponse.data
      : mode === "原始 HTTP 响应" ? httpResponse : { status: "ok", data: httpResponse };
    vi.mocked(apiPost).mockResolvedValue(response);
    expect(await savePluginConfig(receipt.config)).toEqual({ success: true, message: receipt.message });
  });
  it("旧宿主剥离成功标记后仅返回配置时，提示核对而非断言未保存", async () => {
    vi.mocked(apiPost).mockResolvedValue({ prompts: { comic_analysis_prompts: { comic_storyboard_template: "noir_detective" } } });
    expect(await savePluginConfig({})).toEqual({
      success: false,
      message: "保存请求已发送，但无法确认结果。请重新读取配置核对，或刷新页面后重试。",
    });
  });
  it("宿主拒绝保存时保留错误原因", async () => {
    vi.mocked(apiPost).mockRejectedValue(new Error("配置文件写入失败"));
    expect(await savePluginConfig({})).toEqual({ success: false, message: "配置文件写入失败" });
  });
  it.each([null, {}, { data: {} }])("不能将未知响应当作成功：%j", async (response) => {
    vi.mocked(apiPost).mockResolvedValue(response);
    expect((await savePluginConfig({})).success).toBe(false);
  });
});
