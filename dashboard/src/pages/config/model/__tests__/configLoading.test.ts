import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { message } from "antd";
import { fetchPluginConfig, savePluginConfig } from "../../../../entities/config/api/configApi";
import { pluginConfigResponseSchema, pluginConfigSaveSchema } from "../../../../entities/config/model/configContract";
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
    config: { t2i_rendering: { t2i_rendering_strategies: [{ cdn_base_url: value }], extra: "保留" } },
    schema: { t2i_rendering: { type: "object", description: "渲染", items: { t2i_rendering_strategies: { type: "template_list" } } } },
  });
  vi.mocked(savePluginConfig).mockResolvedValue({ success: true });
  const { result } = renderHook(() => useConfigViewModel());
  await waitFor(() => expect(result.current.configLoaded).toBe(true));
  expect(result.current.templateCdnBaseUrl).toBeNull();
  expect(result.current.errors.t2i_rendering.t2i_rendering_strategies).toBeTruthy();
  await act(async () => { await result.current.handleSave(); });
  expect(savePluginConfig).not.toHaveBeenCalled();
  act(() => result.current.handleFieldChange("t2i_rendering", "t2i_rendering_strategies", [{ cdn_base_url: " https://example.com/ " }]));
  expect(result.current.templateCdnBaseUrl).toBe("https://example.com");
  await act(async () => { await result.current.handleSave(); });
  expect(savePluginConfig).toHaveBeenCalledWith(expect.objectContaining({ t2i_rendering: expect.objectContaining({ extra: "保留", t2i_rendering_strategies: [expect.objectContaining({ cdn_base_url: "https://example.com" })] }) }));
  expect(result.current.formData.t2i_rendering.t2i_rendering_strategies).toEqual([expect.objectContaining({ cdn_base_url: "https://example.com" })]);
  expect(result.current.isDirty).toBe(false);
});

it.each([true, false])("清空方案后保存结果为 %s 时，正确更新默认方案或保留未保存草稿", async (success) => {
  const initial = pluginConfigSaveSchema.parse({ t2i_rendering: { t2i_rendering_strategies: schema.t2i_rendering.items.t2i_rendering_strategies.default } }).t2i_rendering!.t2i_rendering_strategies!;
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


it("保存成功后使用新版本，发生冲突时保留用户草稿", async () => {
  const revision = "a".repeat(64);
  const nextRevision = "b".repeat(64);
  vi.mocked(fetchPluginConfig).mockResolvedValue({ config: { basic: { max_topics: 3 } }, schema: {}, revision });
  vi.mocked(savePluginConfig).mockResolvedValueOnce({ success: true, revision: nextRevision });
  const { result } = renderHook(() => useConfigViewModel());
  await waitFor(() => expect(result.current.configLoaded).toBe(true));
  act(() => result.current.handleFieldChange("basic", "max_topics", 5));
  await act(async () => { await result.current.handleSave(); });
  expect(savePluginConfig).toHaveBeenLastCalledWith({ basic: { max_topics: 5 } }, revision);
  expect(result.current.isDirty).toBe(false);
  act(() => result.current.handleFieldChange("basic", "max_topics", 7));
  vi.mocked(savePluginConfig).mockResolvedValueOnce({ success: false, message: "配置已被其他页面修改，请重新读取后再保存。" });
  await act(async () => { await result.current.handleSave(); });
  expect(savePluginConfig).toHaveBeenLastCalledWith({ basic: { max_topics: 7 } }, nextRevision);
  expect(result.current.formData.basic.max_topics).toBe(7);
  expect(result.current.isDirty).toBe(true);
  expect(message.error).toHaveBeenLastCalledWith("配置已被其他页面修改，请重新读取后再保存。");
});


it.each([true, false])("保存排序成功状态 %s：更新展示或保留失败草稿", async (success) => {
  const plans = [{ name: "后执行", priority: 30 }, { name: "同级甲", priority: 10 }, { name: "同级乙", priority: 10 }];
  vi.mocked(fetchPluginConfig).mockResolvedValue(pluginConfigResponseSchema.parse({ config: { t2i_rendering: { t2i_rendering_strategies: plans } }, schema }));
  vi.mocked(savePluginConfig).mockResolvedValue({ success });
  const { result } = renderHook(() => useConfigViewModel());
  await waitFor(() => expect(result.current.configLoaded).toBe(true));
  act(() => result.current.handleFieldChange("t2i_rendering", "t2i_rendering_strategies", plans));
  await act(async () => { await result.current.handleSave(); });
  expect(savePluginConfig).toHaveBeenCalledWith(expect.objectContaining({ t2i_rendering: expect.objectContaining({ t2i_rendering_strategies: [
    expect.objectContaining({ name: "同级甲", priority: 10 }), expect.objectContaining({ name: "同级乙", priority: 10 }), expect.objectContaining({ name: "后执行", priority: 30 }),
  ] }) }));
  expect(result.current.formData.t2i_rendering.t2i_rendering_strategies).toEqual(success ? [expect.objectContaining({ name: "同级甲" }), expect.objectContaining({ name: "同级乙" }), expect.objectContaining({ name: "后执行" })] : plans);
});
