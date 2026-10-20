import { useState } from "react";
import { ConfigProvider } from "antd";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ComicTemplateRotationSettings } from "../ComicTemplateRotationSettings";
import { fetchComicRotationStatus, resetComicRotation } from "../../api/comicRotationApi";
import { fetchDistinctGroups } from "../../../../entities/group/api/groupApi";
import { fetchComicTemplatePreview } from "../../api/comicTemplateApi";
import { COMIC_ROTATION_MODES, type ComicTemplateRotationStatus } from "../../model/comicTemplateRotation";

vi.mock("../../api/comicRotationApi", () => ({ fetchComicRotationStatus: vi.fn(), resetComicRotation: vi.fn() }));
vi.mock("../../api/comicTemplateApi", () => ({ fetchComicTemplatePreview: vi.fn() }));
vi.mock("../../../../entities/group/api/groupApi", () => ({ fetchDistinctGroups: vi.fn() }));
const nativeGetComputedStyle = window.getComputedStyle.bind(window);
const status: ComicTemplateRotationStatus = {
  mode: "sequential", scope: "global", scope_key: "global", candidates: ["classic", "pixel_rpg"], current_template_id: "classic", current_template_name: "原版漫画", next_template_id: "pixel_rpg", next_template_name: "像素 RPG 每日冒险日志", date: "2026-10-17", initialized: true, warning: null,
};
const saved = { comic_template_mode: "sequential", comic_template_scope: "global", comic_template_candidates: ["classic", "pixel_rpg"] };
const openPrompts = vi.fn();

// 已有文本或 aria-label 的控件直接定位，避免 JSDOM 为整棵 AntD DOM 重算可见性。
function buttonWithText(text: string | RegExp): HTMLButtonElement {
  const button = screen.getByText(text).closest("button");
  if (!button) throw new Error(`未找到按钮：${String(text)}`);
  return button;
}

function Editor({ initial = saved, dirty = false }: { initial?: Record<string, unknown>; dirty?: boolean }) {
  const [value, setValue] = useState(initial);
  return <ConfigProvider theme={{ token: { motion: false } }}>
    <ComicTemplateRotationSettings value={value} savedValue={initial} dirty={dirty || value !== initial} customPrompt="我的自定义提示词" onPatch={(patch) => setValue((previous) => ({ ...previous, ...patch }))} onOpenPromptSettings={openPrompts} />
    <output data-testid="comic-draft">{JSON.stringify(value)}</output>
  </ConfigProvider>;
}

describe("漫画模板自动切换设置", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(window, "getComputedStyle").mockImplementation((element) => nativeGetComputedStyle(element));
    vi.mocked(fetchComicRotationStatus).mockResolvedValue(status);
    vi.mocked(fetchDistinctGroups).mockResolvedValue([]);
    vi.mocked(fetchComicTemplatePreview).mockResolvedValue("data:image/webp;base64,YWJj");
    vi.mocked(resetComicRotation).mockResolvedValue({ ...status, initialized: false });
  });
  afterEach(() => vi.restoreAllMocks());

  it("提供六种模式，固定模式沿用原默认模板并保留候选", async () => {
    render(<Editor initial={{ ...saved, comic_template_mode: "fixed" }} />);
    fireEvent.mouseDown(screen.getByLabelText("切换模式"));
    for (const mode of COMIC_ROTATION_MODES) expect(screen.getAllByText(mode.label).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByText("每次随机"));
    expect(screen.getByTestId("comic-draft").textContent).toContain('"comic_template_mode":"random"');
    expect(screen.getByLabelText("漫画模板候选顺序")).toHaveProperty("tagName", "OL");
    fireEvent.click(buttonWithText("编辑自定义提示词"));
    expect(openPrompts).toHaveBeenCalled();
    await waitFor(() => expect(fetchComicRotationStatus).toHaveBeenCalledTimes(1));
    expect(resetComicRotation).not.toHaveBeenCalled();
  });

  it("上下移动和移除改变候选 ID，显示已保存状态并锁定草稿重置", async () => {
    render(<Editor />);
    const reset = buttonWithText("重置进度");
    await waitFor(() => expect(reset).not.toBeDisabled());
    fireEvent.click(screen.getByLabelText("下移原版漫画"));
    expect(JSON.parse(screen.getByTestId("comic-draft").textContent!).comic_template_candidates).toEqual(["pixel_rpg", "classic"]);
    expect(screen.getByText("漫画配置有未保存修改")).toBeInTheDocument();
    expect(reset).toBeDisabled();
    fireEvent.click(screen.getByLabelText("移除原版漫画"));
    expect(JSON.parse(screen.getByTestId("comic-draft").textContent!).comic_template_candidates).toEqual(["pixel_rpg"]);
    expect(screen.getByText("服务器日期")).toBeInTheDocument();
    expect(resetComicRotation).not.toHaveBeenCalled();
  });

  it("画廊添加到候选末尾，预览不推进且保留模板模式", async () => {
    render(<Editor />);
    fireEvent.click(buttonWithText("浏览模板画廊"));
    const gallery = screen.getByText("漫画模板视觉样式画廊").closest<HTMLElement>('[role="dialog"]')!;
    expect(within(gallery).getByLabelText("原版漫画已加入候选")).toBeDisabled();
    fireEvent.click(within(gallery).getByLabelText("添加候选黑色电影侦探风"));
    const draft = JSON.parse(screen.getByTestId("comic-draft").textContent!);
    expect(draft.comic_template_candidates).toEqual(["classic", "pixel_rpg", "noir_detective"]);
    expect(draft.comic_template_mode).toBe("sequential");
    fireEvent.click(await within(gallery).findByLabelText("放大黑色电影侦探风示例图"));
    // rc-dialog 在测试环境复用 test-id，按弹窗实际内容区分叠加的两个对话框。
    const preview = screen.getByText("黑色电影侦探风 · 风格示例").closest<HTMLElement>('[role="dialog"]')!;
    expect(await within(preview).findByAltText("黑色电影侦探风漫画风格示例图")).toBeInTheDocument();
    expect(resetComicRotation).not.toHaveBeenCalled();
    expect(fetchComicRotationStatus).toHaveBeenCalledTimes(1);
  });

  it("每日顺序显示明日模板；重置需要确认且取消不调用 API", async () => {
    vi.mocked(fetchComicRotationStatus).mockResolvedValue({ ...status, mode: "daily_sequential" });
    render(<Editor initial={{ ...saved, comic_template_mode: "daily_sequential" }} />);
    await screen.findByText("明日模板");
    const reset = buttonWithText("重置进度");
    fireEvent.click(reset);
    const cancel = (await screen.findByText(/保\s*留/)).closest("button")!;
    fireEvent.click(cancel);
    await waitFor(() => expect(cancel).not.toBeVisible());
    expect(resetComicRotation).not.toHaveBeenCalled();
    fireEvent.click(reset);
    const buttons = await screen.findAllByText("重置进度");
    fireEvent.click(buttons[buttons.length - 1].closest("button")!);
    await waitFor(() => expect(resetComicRotation).toHaveBeenCalledTimes(1));
  });
});
