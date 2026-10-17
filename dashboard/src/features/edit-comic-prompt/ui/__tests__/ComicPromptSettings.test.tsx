import { useState } from "react";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ComicPromptSettings } from "../ComicPromptSettings";
import { comicPromptTemplates } from "../../model/useComicPromptEditor";
import { fetchComicTemplatePreview } from "../../api/comicTemplateApi";
import { ComicTemplatePreview } from "../ComicTemplatePreview";

vi.mock("../../api/comicTemplateApi", () => ({ fetchComicTemplatePreview: vi.fn() }));
const fetchPreview = vi.mocked(fetchComicTemplatePreview);
const nativeGetComputedStyle = window.getComputedStyle.bind(window);

function Editor({ initial }: { initial: Record<string, unknown> }) {
  const [value, setValue] = useState<unknown>(initial);
  return <ComicPromptSettings value={value} onChange={setValue} idPrefix="comic" />;
}

describe("漫画模板选择器", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, "getComputedStyle").mockImplementation((element) => nativeGetComputedStyle(element));
    fetchPreview.mockImplementation(() => new Promise(() => {}));
  });
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });

  it("显示所有内置模板和自定义选项，切换后保留自定义草稿", () => {
    render(<Editor initial={{ comic_storyboard_prompt: "我的草稿" }} />);
    expect(screen.getByLabelText("自定义漫画场景分析提示词")).toHaveValue("我的草稿");
    fireEvent.mouseDown(screen.getByRole("combobox"));
    for (const preset of comicPromptTemplates) expect(screen.getByText(preset.name)).toBeInTheDocument();
    fireEvent.click(screen.getByText("黑色电影侦探风"));
    expect(screen.queryByLabelText("自定义漫画场景分析提示词")).not.toBeInTheDocument();
    expect(screen.getByLabelText("黑色电影侦探风提示词预览")).toHaveValue(comicPromptTemplates[2].prompt);
    fireEvent.mouseDown(screen.getByRole("combobox"));
    fireEvent.click(screen.getByText("自定义"));
    expect(screen.getByLabelText("自定义漫画场景分析提示词")).toHaveValue("我的草稿");
  });

  it("复制内置模板前可取消并保留原文，确认后可继续编辑", async () => {
    render(<Editor initial={{ comic_storyboard_template: "pixel_rpg", comic_storyboard_prompt: "保留草稿" }} />);
    fireEvent.click(screen.getByRole("button", { name: /复制为自定义/ }));
    fireEvent.click(await screen.findByRole("button", { name: "保留原文" }));
    expect(screen.queryByLabelText("自定义漫画场景分析提示词")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /复制为自定义/ }));
    fireEvent.click(await screen.findByRole("button", { name: "复制并替换" }));
    const editor = screen.getByLabelText("自定义漫画场景分析提示词");
    expect(editor).toHaveValue(comicPromptTemplates[3].prompt);
    fireEvent.change(editor, { target: { value: "修改后的内容" } });
    expect(editor).toHaveValue("修改后的内容");
  });

  it("自定义为空时可直接复制，未知旧选项保留原自定义内容", () => {
    const view = render(<Editor initial={{ comic_storyboard_template: "scp_dossier", comic_storyboard_prompt: "" }} />);
    fireEvent.click(screen.getByRole("button", { name: /复制为自定义/ }));
    expect(screen.getByLabelText("自定义漫画场景分析提示词")).toHaveValue(comicPromptTemplates[1].prompt);
    view.unmount();
    render(<Editor initial={{ comic_storyboard_template: "old_value", comic_storyboard_prompt: "旧内容" }} />);
    expect(screen.getByLabelText("自定义漫画场景分析提示词")).toHaveValue("旧内容");
  });

  it("画廊显示全部风格及选中状态，选用后保留自定义草稿", async () => {
    render(<Editor initial={{ comic_storyboard_template: "noir_detective", comic_storyboard_prompt: "我的原文" }} />);
    fireEvent.click(screen.getByRole("button", { name: /浏览全部模板画廊/ }));
    const gallery = screen.getByRole("dialog", { name: "漫画模板视觉样式画廊" });
    for (const template of comicPromptTemplates) expect(within(gallery).getByText(template.name)).toBeInTheDocument();
    expect(within(gallery).getByRole("button", { name: "黑色电影侦探风当前使用中" })).toBeDisabled();
    fireEvent.click(within(gallery).getByRole("button", { name: "选用像素 RPG 每日冒险日志" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByLabelText("像素 RPG 每日冒险日志提示词预览")).toHaveValue(comicPromptTemplates.find(({ id }) => id === "pixel_rpg")?.prompt);
    fireEvent.mouseDown(screen.getByRole("combobox"));
    fireEvent.click(screen.getByText("自定义"));
    expect(screen.getByLabelText("自定义漫画场景分析提示词")).toHaveValue("我的原文");
  });

  it("自定义预览显示明确空状态且不请求示例图", () => {
    render(<Editor initial={{ comic_storyboard_template: "custom", comic_storyboard_prompt: "内容" }} />);
    fireEvent.click(screen.getByRole("button", { name: /预览当前效果/ }));
    expect(screen.getByText("自定义提示词暂无示例图")).toBeInTheDocument();
    expect(fetchPreview).not.toHaveBeenCalled();
  });

  it("当前缩略图按需加载，打开预览才请求全图，失败可重试", async () => {
    fetchPreview.mockRejectedValueOnce(new Error("网络暂时不可用"));
    fetchPreview.mockResolvedValue("data:image/webp;base64,YWJj");
    render(<Editor initial={{ comic_storyboard_template: "noir_detective" }} />);
    await screen.findByText("加载失败");
    fireEvent.click(screen.getByRole("button", { name: /重试/ }));
    await screen.findByRole("img", { name: "黑色电影侦探风漫画风格示例图" });
    expect(fetchPreview).toHaveBeenCalledWith("noir_detective", "thumbnail", true);
    expect(fetchPreview).not.toHaveBeenCalledWith("noir_detective", "full", expect.anything());
    fireEvent.click(screen.getByRole("button", { name: "放大黑色电影侦探风示例图" }));
    await waitFor(() => expect(fetchPreview).toHaveBeenCalledWith("noir_detective", "full", false));
    expect(screen.getByText(/静态示例图仅供风格参考/)).toBeInTheDocument();
  });

  it("画廊卡片进入可见区域后才请求缩略图", async () => {
    const callbacks: IntersectionObserverCallback[] = [];
    const disconnect = vi.fn();
    vi.stubGlobal("IntersectionObserver", class {
      constructor(callback: IntersectionObserverCallback) { callbacks.push(callback); }
      observe() {}
      disconnect = disconnect;
    });
    fetchPreview.mockResolvedValue("data:image/webp;base64,YWJj");
    render(<ComicTemplatePreview template={comicPromptTemplates[2]} onOpen={() => {}} />);
    expect(fetchPreview).not.toHaveBeenCalled();
    act(() => callbacks[0]([{ isIntersecting: true } as IntersectionObserverEntry], {} as IntersectionObserver));
    await screen.findByRole("img", { name: "黑色电影侦探风漫画风格示例图" });
    expect(fetchPreview).toHaveBeenCalledWith("noir_detective", "thumbnail", false);
    expect(disconnect).toHaveBeenCalled();
  });
});
