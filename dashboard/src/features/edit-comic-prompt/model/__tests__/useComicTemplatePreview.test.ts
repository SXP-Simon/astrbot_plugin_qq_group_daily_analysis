import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fetchComicTemplatePreview } from "../../api/comicTemplateApi";
import { useComicTemplatePreview } from "../useComicTemplatePreview";
import type { ComicPromptTemplate } from "../useComicPromptEditor";

vi.mock("../../api/comicTemplateApi", () => ({ fetchComicTemplatePreview: vi.fn() }));
const fetchPreview = vi.mocked(fetchComicTemplatePreview);
const first: ComicPromptTemplate = { id: "first", name: "模板一", description: "说明", prompt: "正文", preview: "first.webp" };
const second: ComicPromptTemplate = { ...first, id: "second", name: "模板二", preview: "second.webp" };

describe("漫画示例图加载状态", () => {
  beforeEach(() => vi.clearAllMocks());
  afterEach(() => vi.useRealTimers());

  it("自定义和未提供图片的模板不发请求", () => {
    const view = renderHook(({ template }) => useComicTemplatePreview(template, true), {
      initialProps: { template: undefined as ComicPromptTemplate | undefined },
    });
    expect(view.result.current.status).toBe("empty");
    view.rerender({ template: { ...first, preview: undefined } });
    expect(view.result.current.status).toBe("empty");
    expect(fetchPreview).not.toHaveBeenCalled();
  });

  it("切换模板及卸载后忽略过期响应", async () => {
    let finishFirst: ((src: string | null) => void) | undefined;
    let finishSecond: ((src: string | null) => void) | undefined;
    fetchPreview.mockImplementationOnce(() => new Promise((resolve) => { finishFirst = resolve; }));
    fetchPreview.mockImplementationOnce(() => new Promise((resolve) => { finishSecond = resolve; }));
    const view = renderHook(({ template }) => useComicTemplatePreview(template, true, "full"), { initialProps: { template: first } });
    view.rerender({ template: second });
    await act(async () => { finishFirst?.("第一张"); });
    expect(view.result.current.src).toBeUndefined();
    await act(async () => { finishSecond?.("第二张"); });
    expect(view.result.current.src).toBe("第二张");
    expect(fetchPreview).toHaveBeenNthCalledWith(2, "second", "full", false);
    view.unmount();
  });

  it("加载失败可重试，重试强制刷新对应尺寸", async () => {
    fetchPreview.mockRejectedValueOnce(new Error("暂时不可用")).mockResolvedValueOnce("已恢复");
    const { result } = renderHook(() => useComicTemplatePreview(first, true, "thumbnail"));
    await waitFor(() => expect(result.current.status).toBe("error"));
    expect(result.current.error).toBe("暂时不可用");
    act(() => result.current.retry());
    await waitFor(() => expect(result.current.src).toBe("已恢复"));
    expect(fetchPreview).toHaveBeenLastCalledWith("first", "thumbnail", true);
  });

  it("超时结束加载并忽略迟到结果", async () => {
    vi.useFakeTimers();
    let finish: ((src: string | null) => void) | undefined;
    fetchPreview.mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    const { result } = renderHook(() => useComicTemplatePreview(first, true));
    act(() => vi.advanceTimersByTime(15000));
    expect(result.current.status).toBe("error");
    expect(result.current.error).toContain("超时");
    await act(async () => { finish?.("迟到图片"); });
    expect(result.current.src).toBeUndefined();
  });
});
