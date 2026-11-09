import { act, renderHook, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { toast } from "sonner";
import {
  fetchPluginConfig,
  fetchAvailableProviders,
  fetchAvailablePersonas,
  savePluginConfig,
} from "@/entities/config/api/configApi";
import { useConfigViewModel } from "@/pages/config/model/useConfigViewModel";

vi.mock("@/entities/config/api/configApi", () => ({
  fetchPluginConfig: vi.fn(),
  fetchAvailableProviders: vi.fn(),
  fetchAvailablePersonas: vi.fn(),
  savePluginConfig: vi.fn(),
}));
vi.mock("sonner", () => ({ toast: { error: vi.fn(), success: vi.fn(), warning: vi.fn() } }));

const initial: Awaited<ReturnType<typeof fetchPluginConfig>> = {
  config: { basic: { max_topics: 3 } },
  schema: {},
  revision: "a".repeat(64),
};
beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(fetchPluginConfig).mockResolvedValue(initial);
  vi.mocked(fetchAvailableProviders).mockResolvedValue([]);
  vi.mocked(fetchAvailablePersonas).mockResolvedValue([]);
});

it("保存中继续编辑会保留新草稿，同批重复保存和重新读取不会再发请求", async () => {
  let finish!: (value: Awaited<ReturnType<typeof savePluginConfig>>) => void;
  vi.mocked(savePluginConfig).mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const { result } = renderHook(() => useConfigViewModel());
  await waitFor(() => expect(result.current.configLoaded).toBe(true));
  act(() => result.current.handleFieldChange("basic", "max_topics", 5));
  let saving!: Promise<void>;
  act(() => {
    saving = result.current.handleSave();
    void result.current.handleSave();
    void result.current.handleReload();
  });
  expect(savePluginConfig).toHaveBeenCalledTimes(1);
  expect(fetchPluginConfig).toHaveBeenCalledTimes(1);
  act(() => result.current.handleFieldChange("basic", "max_topics", 7));
  await act(async () => {
    finish({ success: true, revision: "b".repeat(64) });
    await saving;
  });
  expect(result.current.formData.basic.max_topics).toBe(7);
  expect(result.current.isDirty).toBe(true);
  expect(result.current.modifiedFields.basic.size).toBe(1);
  expect(result.current.saving).toBe(false);
  vi.mocked(savePluginConfig).mockResolvedValue({ success: true });
  await act(async () => result.current.handleSave());
  expect(savePluginConfig).toHaveBeenLastCalledWith({ basic: { max_topics: 7 } }, "b".repeat(64));
  expect(result.current.isDirty).toBe(false);
  expect(result.current.modifiedFields.basic.size).toBe(0);
});

it("分组计数按一级配置项去重，撤销与保存失败都以已保存快照为基准", async () => {
  vi.mocked(savePluginConfig).mockResolvedValue({ success: false, message: "无法写入" });
  const { result } = renderHook(() => useConfigViewModel());
  await waitFor(() => expect(result.current.configLoaded).toBe(true));
  expect(result.current.modifiedFields.basic.size).toBe(0);
  act(() => result.current.handleFieldChange("basic", "max_topics", 5));
  act(() => result.current.handleFieldChange("basic", "plans", [{ name: "测试", priority: 1 }]));
  act(() => result.current.handleFieldChange("basic", "plans", [{ name: "新名称", priority: 2 }]));
  expect(result.current.modifiedFields.basic.size).toBe(2);
  await act(async () => result.current.handleSave());
  expect(result.current.modifiedFields.basic.size).toBe(2);
  act(() => result.current.handleFieldChange("basic", "max_topics", 3));
  expect([...result.current.modifiedFields.basic]).toEqual(["plans"]);
  act(() => result.current.handleFieldChange("basic", "plans", undefined));
  expect(result.current.modifiedFields.basic.size).toBe(0);
  expect(result.current.isDirty).toBe(false);
});

it("旧读取结果不会覆盖新配置，读取失败保留草稿并禁止保存", async () => {
  let finish!: (value: typeof initial) => void;
  vi.mocked(fetchPluginConfig).mockReturnValueOnce(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const { result } = renderHook(() => useConfigViewModel());
  await act(async () => result.current.handleReload());
  act(() => result.current.handleFieldChange("basic", "max_topics", 9));
  await act(async () => finish({ ...initial, config: { basic: { max_topics: 1 } } }));
  expect(result.current.formData.basic.max_topics).toBe(9);
  vi.mocked(fetchPluginConfig).mockRejectedValueOnce(new Error("读取超时"));
  await act(async () => result.current.handleReload());
  expect(result.current.loadError).toBe("读取超时");
  expect(result.current.formData.basic.max_topics).toBe(9);
  expect(result.current.isDirty).toBe(true);
  await act(async () => result.current.handleSave());
  expect(savePluginConfig).not.toHaveBeenCalled();
});

it("模型选项读取失败不清空配置，并明确提示；重试成功后清除提示", async () => {
  vi.mocked(fetchAvailableProviders).mockRejectedValueOnce(new Error("offline"));
  const { result } = renderHook(() => useConfigViewModel());
  await waitFor(() => expect(result.current.configLoaded).toBe(true));
  expect(result.current.optionsError).toContain("模型选项暂时无法读取");
  expect(result.current.formData).toEqual(initial.config);
  await act(async () => result.current.handleReload());
  expect(result.current.optionsError).toBe("");
});

it("保存成功后的页面刷新失败不会冒充保存失败", async () => {
  const callback = vi.fn().mockRejectedValue(new Error("刷新失败"));
  vi.mocked(savePluginConfig).mockResolvedValue({ success: true });
  const { result } = renderHook(() => useConfigViewModel(callback));
  await waitFor(() => expect(result.current.configLoaded).toBe(true));
  act(() => result.current.handleFieldChange("basic", "max_topics", 5));
  await act(async () => result.current.handleSave());
  expect(result.current.isDirty).toBe(false);
  expect(result.current.saveError).toBe("");
  expect(toast.success).toHaveBeenCalledOnce();
  expect(toast.warning).toHaveBeenCalledWith("配置已保存，但相关页面未能刷新，请手动刷新查看。");
  expect(toast.error).not.toHaveBeenCalled();
});

it("卸载后到达的保存结果不会通知或触发其他页面刷新", async () => {
  let finish!: (value: Awaited<ReturnType<typeof savePluginConfig>>) => void;
  vi.mocked(savePluginConfig).mockReturnValue(
    new Promise((resolve) => {
      finish = resolve;
    }),
  );
  const callback = vi.fn();
  const { result, unmount } = renderHook(() => useConfigViewModel(callback));
  await waitFor(() => expect(result.current.configLoaded).toBe(true));
  let saving!: Promise<void>;
  act(() => {
    saving = result.current.handleSave();
  });
  unmount();
  await act(async () => {
    finish({ success: true });
    await saving;
  });
  expect(callback).not.toHaveBeenCalled();
  expect(toast.success).not.toHaveBeenCalled();
  expect(toast.error).not.toHaveBeenCalled();
});
