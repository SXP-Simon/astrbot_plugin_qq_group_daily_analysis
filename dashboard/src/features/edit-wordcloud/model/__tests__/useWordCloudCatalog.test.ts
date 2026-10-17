import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchWordCloudCatalog, previewWordCloud } from "../../../../entities/wordcloud/api/wordCloudApi";
import type { WordCloudCatalog } from "../../../../entities/wordcloud/model/types";
import { useWordCloudCatalog } from "../useWordCloudCatalog";

vi.mock("../../../../entities/wordcloud/api/wordCloudApi", () => ({
  fetchWordCloudCatalog: vi.fn(),
  previewWordCloud: vi.fn(),
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

const catalog: WordCloudCatalog = {
  templates: [{ name: "ATRI", label: "亚托莉 (ATRI)" }],
  fonts: [{ id: "wenkai", label: "霞鹜文楷" }, { id: "uploaded:abc.woff2", label: "自定义字体" }],
};

afterEach(() => { vi.resetAllMocks(); });

describe("普通配置页的词云选项目录", () => {
  it("仅进入词云页时读取目录，且不会触发预览", async () => {
    vi.mocked(fetchWordCloudCatalog).mockResolvedValue(catalog);
    const { result, rerender } = renderHook(({ active }) => useWordCloudCatalog({ active }), { initialProps: { active: false } });
    expect(fetchWordCloudCatalog).not.toHaveBeenCalled();
    expect(result.current.loading).toBe(false);
    rerender({ active: true });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(fetchWordCloudCatalog).toHaveBeenCalledTimes(1);
    expect(result.current.fontOptions).toContainEqual({ value: "uploaded:abc.woff2", label: "自定义字体" });
    expect(previewWordCloud).not.toHaveBeenCalled();
  });

  it("读取失败仍保留当前配置与内置选项，并可重试", async () => {
    vi.mocked(fetchWordCloudCatalog).mockRejectedValueOnce(new Error("目录暂不可用")).mockResolvedValueOnce(catalog);
    const { result } = renderHook(() => useWordCloudCatalog({ active: true, template: "MissingTheme", font: "uploaded:abc.woff2" }));
    await waitFor(() => expect(result.current.error).toBe("目录暂不可用"));
    expect(result.current.templateOptions.map((item) => item.value)).toEqual(["ATRI", "MissingTheme"]);
    expect(result.current.fontOptions.map((item) => item.value)).toEqual(["wenkai", "sans", "serif", "uploaded:abc.woff2"]);
    act(() => result.current.refresh());
    await waitFor(() => expect(result.current.error).toBe(""));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.fontOptions).toContainEqual({ value: "uploaded:abc.woff2", label: "自定义字体" });
    expect(result.current.templateOptions.map((item) => item.value)).toContain("MissingTheme");
  });

  it("编辑器关闭后重新读取上传字体，晚返回的旧目录不能覆盖新目录", async () => {
    const old = deferred<WordCloudCatalog>();
    const recent = deferred<WordCloudCatalog>();
    vi.mocked(fetchWordCloudCatalog).mockReturnValueOnce(old.promise).mockReturnValueOnce(recent.promise);
    const { result, rerender } = renderHook(({ revision }) => useWordCloudCatalog({ active: true, font: "uploaded:abc.woff2", revision }), { initialProps: { revision: 0 } });
    rerender({ revision: 1 });
    await act(async () => { recent.resolve(catalog); });
    expect(result.current.fontOptions).toContainEqual({ value: "uploaded:abc.woff2", label: "自定义字体" });
    await act(async () => { old.resolve({ templates: [], fonts: [] }); });
    expect(result.current.fontOptions).toContainEqual({ value: "uploaded:abc.woff2", label: "自定义字体" });
    expect(result.current.loading).toBe(false);
  });

  it("目录成功返回空列表时保留当前值，修改选择不会重复请求", async () => {
    vi.mocked(fetchWordCloudCatalog).mockResolvedValue({ templates: [], fonts: [] });
    const { result, rerender } = renderHook(({ font }) => useWordCloudCatalog({ active: true, template: "Custom", font }), { initialProps: { font: "uploaded:old.ttf" } });
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.templateOptions.map((item) => item.value)).toEqual(["Custom"]);
    expect(result.current.fontOptions.map((item) => item.value)).toEqual(["uploaded:old.ttf"]);
    rerender({ font: "uploaded:new.ttf" });
    expect(result.current.fontOptions.map((item) => item.value)).toEqual(["uploaded:new.ttf"]);
    expect(fetchWordCloudCatalog).toHaveBeenCalledTimes(1);
  });

  it("离开词云页后丢弃未完成的目录请求", async () => {
    const pending = deferred<WordCloudCatalog>();
    vi.mocked(fetchWordCloudCatalog).mockReturnValue(pending.promise);
    const { result, rerender } = renderHook(({ active }) => useWordCloudCatalog({ active }), { initialProps: { active: true } });
    expect(result.current.loading).toBe(true);
    rerender({ active: false });
    await act(async () => { pending.resolve(catalog); });
    expect(result.current.loading).toBe(false);
    expect(result.current.fontOptions.some((item) => item.value === "uploaded:abc.woff2")).toBe(false);
  });

  it("刷新失败后仍保留上次成功读取的上传字体选项", async () => {
    vi.mocked(fetchWordCloudCatalog).mockResolvedValueOnce(catalog).mockRejectedValueOnce("网络错误");
    const { result } = renderHook(() => useWordCloudCatalog({ active: true }));
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.refresh());
    await waitFor(() => expect(result.current.error).toBe("读取词云模板和字体失败，请重试"));
    expect(result.current.fontOptions).toContainEqual({ value: "uploaded:abc.woff2", label: "自定义字体" });
  });
});
