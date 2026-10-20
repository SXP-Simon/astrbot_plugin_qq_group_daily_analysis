import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchDistinctGroups } from "../../../../entities/group/api/groupApi";
import { fetchWordCloudCatalog } from "../../../../entities/wordcloud/api/wordCloudApi";
import { useWordCloudGroupOverrides } from "../useWordCloudGroupOverrides";

vi.mock("../../../../entities/group/api/groupApi", () => ({ fetchDistinctGroups: vi.fn() }));
vi.mock("../../../../entities/wordcloud/api/wordCloudApi", () => ({ fetchWordCloudCatalog: vi.fn() }));
afterEach(() => { vi.resetAllMocks(); });

describe("群级词云覆盖交互", () => {
  it("未打开时不读取群列表；选择群不会改写配置，修改仅回传覆盖对象", async () => {
    vi.mocked(fetchDistinctGroups).mockResolvedValue([{ platform: "bot", group_id: "123", group_name: "测试群" }]);
    vi.mocked(fetchWordCloudCatalog).mockResolvedValue({ templates: [{ name: "ATRI", label: "亚托莉" }], fonts: [] });
    const onChange = vi.fn();
    const { result, rerender } = renderHook(({ active }) => useWordCloudGroupOverrides({ active, value: { "offline:GroupMessage:999": { font: "serif" } }, globalValue: { word_spacing: 7 }, onChange }), { initialProps: { active: false } });
    expect(fetchDistinctGroups).not.toHaveBeenCalled();
    rerender({ active: true });
    await waitFor(() => expect(result.current.options).toHaveLength(2));
    expect(fetchWordCloudCatalog).not.toHaveBeenCalled();
    act(() => result.current.setSelected("bot:GroupMessage:123"));
    await waitFor(() => expect(result.current.catalog.loading).toBe(false));
    expect(onChange).not.toHaveBeenCalled();
    act(() => result.current.setFields(["word_spacing"]));
    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith({ "offline:GroupMessage:999": { font: "serif" }, "bot:GroupMessage:123": { word_spacing: 7 } });
  });

  it("群列表失败仍允许选择已有群，且显示当前上传字体", async () => {
    vi.mocked(fetchDistinctGroups).mockRejectedValue(new Error("暂时离线"));
    vi.mocked(fetchWordCloudCatalog).mockResolvedValue({ templates: [], fonts: [] });
    const onChange = vi.fn();
    const umo = "offline:GroupMessage:999";
    const { result } = renderHook(() => useWordCloudGroupOverrides({ value: { [umo]: { font: "uploaded:old.woff2" } }, onChange }));
    await waitFor(() => expect(result.current.loadError).toBe("暂时离线"));
    act(() => result.current.setSelected(umo));
    await waitFor(() => expect(result.current.catalog.loading).toBe(false));
    expect(result.current.catalog.fontOptions.map((option) => option.value)).toContain("uploaded:old.woff2");
    expect(result.current.locked).toBe(false);
    expect(onChange).not.toHaveBeenCalled();
  });

  it("格式错误的根配置和群配置保持原样并锁定编辑", async () => {
    vi.mocked(fetchDistinctGroups).mockResolvedValue([]);
    vi.mocked(fetchWordCloudCatalog).mockResolvedValue({ templates: [], fonts: [] });
    const onChange = vi.fn();
    const { result, rerender } = renderHook(({ value }: { value: unknown }) => useWordCloudGroupOverrides({ value, onChange }), { initialProps: { value: "old invalid config" as unknown } });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.malformed).toBe(true);
    rerender({ value: { "bot:GroupMessage:123": ["legacy"] } });
    act(() => result.current.setSelected("bot:GroupMessage:123"));
    await waitFor(() => expect(result.current.catalog.loading).toBe(false));
    expect(result.current.invalidGroup).toBe(true);
    act(() => result.current.update("font", "sans"));
    expect(onChange).not.toHaveBeenCalled();
  });
});
