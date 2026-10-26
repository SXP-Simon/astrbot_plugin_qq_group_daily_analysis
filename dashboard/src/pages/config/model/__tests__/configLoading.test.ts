import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { message } from "antd";
import { fetchPluginConfig, savePluginConfig } from "../../../../entities/config/api/configApi";
import { pluginConfigResponseSchema } from "../../../../entities/config/model/configContract";
import { useConfigViewModel } from "../useConfigViewModel";
import schema from "../../../../../../_conf_schema.json";

vi.mock("../../../../entities/config/api/configApi", () => ({
  fetchPluginConfig: vi.fn(), savePluginConfig: vi.fn(),
  fetchAvailableProviders: vi.fn().mockResolvedValue([]),
  fetchAvailablePersonas: vi.fn().mockResolvedValue([]),
}));
vi.mock("antd", () => ({ message: { error: vi.fn(), success: vi.fn() } }));

beforeEach(() => vi.clearAllMocks());

it("加载失败要提示且禁止保存空配置", async () => {
  vi.mocked(fetchPluginConfig).mockRejectedValue(new Error("配置响应结构无效"));
  const { result } = renderHook(() => useConfigViewModel());
  await waitFor(() => expect(result.current.loading).toBe(false));
  expect(message.error).toHaveBeenCalledWith("配置响应结构无效");
  await act(async () => { await result.current.handleSave(); });
  expect(savePluginConfig).not.toHaveBeenCalled();
});

it.each(["wrong", 123, null])("CDN 草稿错误 %j 不会驱动默认预览，修正后保存规范化值", async (value) => {
  vi.mocked(fetchPluginConfig).mockResolvedValue({
    config: { t2i_rendering: { t2i_cdn_base_url: value, extra: "保留" } },
    schema: { t2i_rendering: { type: "object", description: "渲染", items: { t2i_cdn_base_url: { type: "string" } } } },
  });
  vi.mocked(savePluginConfig).mockResolvedValue({ success: true });
  const { result } = renderHook(() => useConfigViewModel());
  await waitFor(() => expect(result.current.configLoaded).toBe(true));
  expect(result.current.templateCdnBaseUrl).toBeNull();
  expect(result.current.errors.t2i_rendering.t2i_cdn_base_url).toBeTruthy();
  await act(async () => { await result.current.handleSave(); });
  expect(savePluginConfig).not.toHaveBeenCalled();
  act(() => result.current.handleFieldChange("t2i_rendering", "t2i_cdn_base_url", " https://example.com/ "));
  expect(result.current.templateCdnBaseUrl).toBe("https://example.com");
  await act(async () => { await result.current.handleSave(); });
  expect(savePluginConfig).toHaveBeenCalledWith({ t2i_rendering: { t2i_cdn_base_url: "https://example.com", extra: "保留" } });
  expect(result.current.formData.t2i_rendering.t2i_cdn_base_url).toBe("https://example.com");
  expect(result.current.isDirty).toBe(false);
});

it.each([true, false])("清空方案后保存结果为 %s 时，正确更新默认方案或保留未保存草稿", async (success) => {
  const initial = schema.t2i_rendering.items.t2i_rendering_strategies.default;
  vi.mocked(fetchPluginConfig).mockResolvedValue(pluginConfigResponseSchema.parse({
    config: { t2i_rendering: { t2i_rendering_strategies: initial } }, schema,
  }));
  vi.mocked(savePluginConfig).mockResolvedValue({ success });
  const { result } = renderHook(() => useConfigViewModel());
  await waitFor(() => expect(result.current.configLoaded).toBe(true));
  act(() => result.current.handleFieldChange("t2i_rendering", "t2i_rendering_strategies", []));
  expect(result.current.isDirty).toBe(true);
  await act(async () => { await result.current.handleSave(); });
  expect(savePluginConfig).toHaveBeenCalledWith({ t2i_rendering: { t2i_rendering_strategies: initial } });
  expect(result.current.formData.t2i_rendering.t2i_rendering_strategies).toEqual(success ? initial : []);
  expect(result.current.isDirty).toBe(!success);
  expect(message.success).toHaveBeenCalledTimes(success ? 1 : 0);
});
