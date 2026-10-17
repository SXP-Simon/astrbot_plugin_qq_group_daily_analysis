import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useWordCloudEditor } from "../useWordCloudEditor";
import { previewWordCloud, fetchWordCloudCatalog, deleteWordCloudFont } from "../../../../entities/wordcloud/api/wordCloudApi";
import type { WordCloudPreview } from "../../../../entities/wordcloud/model/types";
import { pluginConfigSaveSchema } from "../../../../entities/config/model/configContract";
import { measureWordCloudHtml } from "../wordCloudLayout";

vi.mock("../wordCloudLayout", async (original) => ({ ...await original<typeof import("../wordCloudLayout")>(), measureWordCloudHtml: vi.fn() }));

vi.mock("../../../../entities/wordcloud/api/wordCloudApi", () => ({
  fetchWordCloudCatalog: vi.fn(),
  previewWordCloud: vi.fn(),
  uploadWordCloudFont: vi.fn(),
  fetchWordCloudSnapshots: vi.fn().mockResolvedValue([]),
  previewWordCloudFont: vi.fn().mockResolvedValue({ html: "样张", font: "wenkai" }),
  renameWordCloudFont: vi.fn(),
  deleteWordCloudFont: vi.fn(),
  restoreWordCloudFont: vi.fn(),
}));

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => { resolve = done; });
  return { promise, resolve };
}

describe("词云草稿的异步预览", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.mocked(fetchWordCloudCatalog).mockResolvedValue({ templates: [{ name: "ATRI", label: "ATRI" }], fonts: [] });
  });
  afterEach(() => { vi.useRealTimers(); vi.clearAllMocks(); });

  it("旧 HTML 请求晚返回时不会覆盖新草稿", async () => {
    const old = deferred<WordCloudPreview>();
    const recent = deferred<WordCloudPreview>();
    vi.mocked(previewWordCloud).mockReturnValueOnce(old.promise).mockReturnValueOnce(recent.promise);
    const { result, rerender } = renderHook(({ spacing }) => useWordCloudEditor({ word_spacing: spacing }, vi.fn(), vi.fn()), { initialProps: { spacing: 10 } });
    await act(async () => { await vi.advanceTimersByTimeAsync(350); });
    rerender({ spacing: 20 });
    await act(async () => { await vi.advanceTimersByTimeAsync(350); });
    await act(async () => { recent.resolve({ html: "新草稿" }); });
    expect(result.current.htmlPreview?.html).toBe("新草稿");
    await act(async () => { old.resolve({ html: "旧草稿" }); });
    expect(result.current.htmlPreview?.html).toBe("新草稿");
  });

  it("T2I 使用未保存的草稿，并丢弃渲染期间已过期的图片", async () => {
    const rendered = deferred<WordCloudPreview>();
    vi.mocked(previewWordCloud).mockImplementation((_options, mode) => mode === "image" ? rendered.promise : Promise.resolve({ html: "预览" }));
    const { result, rerender } = renderHook(({ spacing }) => useWordCloudEditor({ word_spacing: spacing }, vi.fn(), vi.fn()), { initialProps: { spacing: 7 } });
    await act(async () => { void result.current.renderImage(); });
    expect(previewWordCloud).toHaveBeenCalledWith(expect.objectContaining({ word_spacing: 7 }), "image", { source: "sample", umo: undefined });
    rerender({ spacing: 15 });
    await act(async () => { rendered.resolve({ image: "data:image/png;base64,old" }); });
    expect(result.current.image).toBeNull();
    expect(result.current.imageLoading).toBe(false);
  });

  it("请求阶段超时后退出加载状态，刷新可重新创建预览", async () => {
    vi.mocked(previewWordCloud).mockRejectedValueOnce(new Error("请求词云预览超时，请刷新预览后重试")).mockResolvedValueOnce({ html: "重试成功" });
    const { result } = renderHook(() => useWordCloudEditor({}, vi.fn(), vi.fn()));
    await act(async () => { await vi.advanceTimersByTimeAsync(350); });
    expect(result.current.htmlPreview).toBeNull();
    expect(result.current.previewState).toBe("error");
    expect(result.current.previewError).toContain("请求词云预览超时");
    act(() => { result.current.refresh(); });
    expect(result.current.previewState).toBe("loading");
    expect(result.current.previewError).toBe("");
    await act(async () => { await vi.advanceTimersByTimeAsync(350); });
    expect(result.current.htmlPreview?.html).toBe("重试成功");
  });

  it("快速拖动间距只请求最后一次草稿", async () => {
    vi.mocked(previewWordCloud).mockResolvedValue({ html: "预览" });
    const { rerender } = renderHook(({ spacing }) => useWordCloudEditor({ word_spacing: spacing }, vi.fn(), vi.fn()), { initialProps: { spacing: 10 } });
    await act(async () => { await vi.advanceTimersByTimeAsync(100); });
    rerender({ spacing: 9 });
    await act(async () => { await vi.advanceTimersByTimeAsync(100); });
    rerender({ spacing: 8 });
    await act(async () => { await vi.advanceTimersByTimeAsync(350); });
    expect(previewWordCloud).toHaveBeenCalledTimes(1);
    expect(previewWordCloud).toHaveBeenCalledWith(expect.objectContaining({ word_spacing: 8 }), "html", { source: "sample", umo: undefined });
  });

  it("错误字段保留原值且阻止 HTML 与 T2I 预览", async () => {
    const { result } = renderHook(() => useWordCloudEditor({ min_font_size: 130, max_font_size: 80, font: "serif", word_spacing: 6 }, vi.fn(), vi.fn()));
    await act(async () => { await vi.advanceTimersByTimeAsync(350); await result.current.renderImage(); });
    expect(result.current.options).toMatchObject({ min_font_size: 130, max_font_size: 80, font: "serif", word_spacing: 6 });
    expect(result.current.fieldErrors.min_font_size).toContain("不能超过");
    expect(previewWordCloud).not.toHaveBeenCalled();
  });

  it("预设作为一个外观补丁应用，撤销不会覆盖后续手动改动", async () => {
    const patch = vi.fn();
    const { result, rerender } = renderHook(({ value }) => useWordCloudEditor(value, vi.fn(), patch), { initialProps: { value: { word_spacing: 10, min_font_size: 34, max_font_size: 90, max_words: 80, min_frequency: 9 } } });
    await act(async () => { result.current.applyPreset("compact"); });
    expect(patch).toHaveBeenCalledTimes(1);
    expect(patch).toHaveBeenLastCalledWith({ word_spacing: 3, min_font_size: 24, max_font_size: 72, max_words: 120 });
    rerender({ value: { word_spacing: 7, min_font_size: 24, max_font_size: 72, max_words: 120, min_frequency: 9 } });
    await act(async () => { result.current.undo(); });
    expect(patch).toHaveBeenLastCalledWith({ min_font_size: 34, max_font_size: 90, max_words: 80 });
  });

  it("切换真实群缓存时不接受旧来源的预览", async () => {
    const old = deferred<WordCloudPreview>();
    vi.mocked(previewWordCloud).mockReturnValueOnce(old.promise).mockResolvedValueOnce({ html: "真实群缓存" });
    const { result } = renderHook(() => useWordCloudEditor({}, vi.fn(), vi.fn()));
    await act(async () => { await vi.advanceTimersByTimeAsync(350); });
    act(() => { result.current.setSourceId("snapshot-123"); });
    await act(async () => { await vi.advanceTimersByTimeAsync(350); });
    expect(previewWordCloud).toHaveBeenLastCalledWith(expect.anything(), "html", { source: "snapshot", snapshot_id: "snapshot-123", umo: undefined });
    await act(async () => { old.resolve({ html: "旧示例" }); });
    expect(result.current.htmlPreview?.html).toBe("真实群缓存");
  });

  it("群级预设撤销重新继承原本未覆盖的字段", async () => {
    const patch = vi.fn();
    const { result, rerender } = renderHook(({ spacing, overrideKeys }) => useWordCloudEditor({ word_spacing: spacing, font: "serif" }, vi.fn(), patch, "qa:group", [], overrideKeys), { initialProps: { spacing: 10, overrideKeys: ["font"] } });
    await act(async () => { result.current.applyPreset("compact"); });
    rerender({ spacing: 3, overrideKeys: ["font", "word_spacing", "min_font_size", "max_font_size", "max_words"] });
    await act(async () => { result.current.undo(); });
    expect(patch).toHaveBeenLastCalledWith({ word_spacing: undefined });
    expect(patch.mock.calls[1][0]).not.toHaveProperty("font");
  });

  it("未保存的群级引用阻止字体删除", async () => {
    const { result } = renderHook(() => useWordCloudEditor({ font: "wenkai" }, vi.fn(), vi.fn(), undefined, ["uploaded:protected.woff2"]));
    await act(async () => { await result.current.deleteFont("uploaded:protected.woff2"); });
    expect(deleteWordCloudFont).not.toHaveBeenCalled();
  });

  it("自动紧凑调整按真实排入数选择最佳结果，并在完成后原子应用", async () => {
    vi.mocked(previewWordCloud).mockResolvedValue({ html: "候选预览" });
    vi.mocked(measureWordCloudHtml).mockResolvedValueOnce({ placed: 20, total: 80 }).mockResolvedValueOnce({ placed: 35, total: 80 }).mockResolvedValueOnce({ placed: 32, total: 80 }).mockResolvedValueOnce({ placed: 60, total: 80 });
    const patch = vi.fn();
    const { result } = renderHook(() => useWordCloudEditor({}, vi.fn(), patch));
    await act(async () => { await vi.advanceTimersByTimeAsync(350); });
    const frame = document.createElement("iframe");
    document.body.appendChild(frame);
    result.current.iframeRef.current = frame;
    act(() => { window.dispatchEvent(new MessageEvent("message", { source: frame.contentWindow, data: { type: "wordcloud-render-state", state: "ready", placed: 20, total: 80 } })); });
    await act(async () => { await result.current.fitMore(); });
    expect(measureWordCloudHtml).toHaveBeenCalledTimes(4);
    expect(patch).toHaveBeenCalledTimes(1);
    expect(patch).toHaveBeenCalledWith({ word_spacing: 0, min_font_size: 25, max_font_size: 67 });
    expect(result.current.fitNotice).toContain("60");
    frame.remove();
  });

  it("自动调整中修改草稿会取消迟到结果", async () => {
    const measured = deferred<{ placed: number; total: number }>();
    vi.mocked(previewWordCloud).mockResolvedValue({ html: "候选预览" });
    vi.mocked(measureWordCloudHtml).mockReturnValue(measured.promise);
    const patch = vi.fn();
    const { result, rerender } = renderHook(({ spacing }) => useWordCloudEditor({ word_spacing: spacing }, vi.fn(), patch), { initialProps: { spacing: 10 } });
    await act(async () => { await vi.advanceTimersByTimeAsync(350); });
    const frame = document.createElement("iframe");
    document.body.appendChild(frame);
    result.current.iframeRef.current = frame;
    act(() => { window.dispatchEvent(new MessageEvent("message", { source: frame.contentWindow, data: { type: "wordcloud-render-state", state: "ready", placed: 20, total: 80 } })); });
    await act(async () => { void result.current.fitMore(); });
    rerender({ spacing: 14 });
    await act(async () => { measured.resolve({ placed: 80, total: 80 }); });
    expect(patch).not.toHaveBeenCalled();
    expect(result.current.fitProgress).toBe("");
    frame.remove();
  });
});

describe("词云配置保存兼容性", () => {
  it("新增默认值时保留其他分组、未识别词云字段及群级覆盖", () => {
    const overrides = { "aiocqhttp:GroupMessage:123456": { word_spacing: 4 } };
    const saved = pluginConfigSaveSchema.parse({
      basic: { test_option: "保持原值" },
      wordcloud: { word_spacing: 0, group_overrides: overrides, future_option: true },
    });
    expect(saved.basic).toEqual({ test_option: "保持原值" });
    expect(saved.wordcloud).toMatchObject({ word_spacing: 0, group_overrides: overrides, future_option: true, font: "wenkai", max_words: 80 });
  });
});
