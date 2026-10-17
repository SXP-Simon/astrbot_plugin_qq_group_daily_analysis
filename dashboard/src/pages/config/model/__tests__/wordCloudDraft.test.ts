import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { fetchPluginConfig, savePluginConfig } from "../../../../entities/config/api/configApi";
import type { PluginSchema } from "../../../../entities/config/model/types";
import { validateConfigWithZod } from "../../../../entities/config/model/validation";
import { useConfigViewModel } from "../useConfigViewModel";

vi.mock("../../../../entities/config/api/configApi", () => ({
  fetchPluginConfig: vi.fn(), savePluginConfig: vi.fn(),
  fetchAvailableProviders: vi.fn().mockResolvedValue([]), fetchAvailablePersonas: vi.fn().mockResolvedValue([]),
}));
vi.mock("antd", () => ({ message: { error: vi.fn(), success: vi.fn() } }));

const font = `uploaded:${"a".repeat(64)}.woff2`;
const schema: PluginSchema = {
  wordcloud: { type: "object", description: "词云", items: {
    font: { type: "string", options: ["wenkai", "sans", "serif"] },
    template: { type: "string", options: ["ATRI"] },
    min_font_size: { type: "int" }, max_font_size: { type: "int" }, group_overrides: { type: "dict" },
  } },
};
const original = { wordcloud: { font, template: "custom_theme", min_font_size: 34, max_font_size: 90, future: "保留", group_overrides: { "qq:GroupMessage:123": { word_spacing: 4 } } }, basic: { extra: 1 } };
beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(fetchPluginConfig).mockResolvedValue({ config: structuredClone(original), schema });
  vi.mocked(savePluginConfig).mockResolvedValue({ success: true });
});

it("静态宿主选项不阻止控制台保存上传字体与新增主题", () => {
  expect(validateConfigWithZod(original, schema).isValid).toBe(true);
  expect(validateConfigWithZod({ wordcloud: { font: "uploaded:../bad.woff" } }, schema).isValid).toBe(false);
});

it("外观补丁与撤销保留群覆盖、未知字段和其他分组草稿", async () => {
  const { result } = renderHook(() => useConfigViewModel());
  await waitFor(() => expect(result.current.configLoaded).toBe(true));
  act(() => {
    result.current.handleFieldChange("basic", "extra", 2);
    result.current.handleGroupPatch("wordcloud", { min_font_size: 24, max_font_size: 76 });
  });
  expect(result.current.formData.wordcloud).toMatchObject({ min_font_size: 24, max_font_size: 76, future: "保留", group_overrides: original.wordcloud.group_overrides });
  expect(result.current.wordCloudDirty).toBe(true);
  act(() => result.current.restoreSavedWordCloud());
  expect(result.current.formData.wordcloud).toEqual(original.wordcloud);
  expect(result.current.formData.basic.extra).toBe(2);
  expect(result.current.wordCloudDirty).toBe(false);
  expect(result.current.isDirty).toBe(true);
});

it("有草稿时重新读取先确认，取消保留输入，确认后才重新请求", async () => {
  const { result } = renderHook(() => useConfigViewModel());
  await waitFor(() => expect(result.current.configLoaded).toBe(true));
  act(() => result.current.handleGroupPatch("wordcloud", { word_spacing: 3 }));
  act(() => result.current.handleReload());
  expect(result.current.reloadConfirmationOpen).toBe(true);
  expect(fetchPluginConfig).toHaveBeenCalledTimes(1);
  act(() => result.current.cancelReload());
  expect(result.current.formData.wordcloud.word_spacing).toBe(3);
  act(() => result.current.handleReload());
  await act(async () => { await result.current.confirmReload(); });
  expect(fetchPluginConfig).toHaveBeenCalledTimes(2);
  expect(result.current.isDirty).toBe(false);
});

it("草稿期间注册离页保护，恢复保存状态后解除", async () => {
  const { result } = renderHook(() => useConfigViewModel());
  await waitFor(() => expect(result.current.configLoaded).toBe(true));
  act(() => result.current.handleGroupPatch("wordcloud", { max_words: 120 }));
  const dirtyEvent = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(dirtyEvent);
  expect(dirtyEvent.defaultPrevented).toBe(true);
  act(() => result.current.restoreSavedWordCloud());
  const cleanEvent = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(cleanEvent);
  expect(cleanEvent.defaultPrevented).toBe(false);
});

it("全局改动与群继承发生字号冲突时阻止保存并标记群覆盖", async () => {
  const { result } = renderHook(() => useConfigViewModel());
  await waitFor(() => expect(result.current.configLoaded).toBe(true));
  act(() => result.current.handleGroupPatch("wordcloud", { max_font_size: 50, group_overrides: { "qq:GroupMessage:123": { min_font_size: 70 } } }));
  expect(result.current.errors.wordcloud.group_overrides).toContain("123");
  await act(async () => { await result.current.handleSave(); });
  expect(savePluginConfig).not.toHaveBeenCalled();
});

it("不完整 JSON 与 null 群覆盖草稿保留现场并阻止保存", async () => {
  const { result } = renderHook(() => useConfigViewModel());
  await waitFor(() => expect(result.current.configLoaded).toBe(true));
  for (const draft of ['{"qq:GroupMessage:123":', null]) {
    act(() => result.current.handleFieldChange("wordcloud", "group_overrides", draft));
    expect(result.current.formData.wordcloud.group_overrides).toEqual(draft);
    expect(result.current.wordCloudDirty).toBe(true);
    expect(result.current.errors.wordcloud.group_overrides).toBeTruthy();
    await act(async () => { await result.current.handleSave(); });
  }
  expect(savePluginConfig).not.toHaveBeenCalled();
});
