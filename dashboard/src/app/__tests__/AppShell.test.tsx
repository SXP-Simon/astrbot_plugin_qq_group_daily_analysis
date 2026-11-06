import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "../ui/AppShell";
import { usePageNavigation } from "../model/usePageNavigation";

function Fixture() {
  const { page, visited, navigate } = usePageNavigation("overview");
  return (
    <AppShell
      activePage={page}
      visited={visited}
      onNavigate={navigate}
      onRefresh={() => {}}
      onOpenTrigger={() => {}}
      loading={false}
      items={[
        { key: "overview", label: "总览", icon: null, children: <input aria-label="筛选群聊" /> },
        { key: "config", label: "配置", icon: null, children: <textarea aria-label="配置草稿" /> },
        { key: "logs", label: "日志", icon: null, children: <p>示例日志</p> },
      ]}
    />
  );
}

describe("正式页面导航", () => {
  afterEach(() => vi.restoreAllMocks());

  it("快速切页以最后一次为准，往返保留输入和滚动位置", () => {
    const scroll = vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    const scrollY = vi.spyOn(window, "scrollY", "get").mockReturnValue(0);
    render(<Fixture />);
    fireEvent.change(screen.getByRole("textbox", { name: "筛选群聊" }), {
      target: { value: "示例群" },
    });
    scrollY.mockReturnValue(420);
    fireEvent.mouseDown(screen.getByRole("tab", { name: "配置" }), { button: 0, ctrlKey: false });
    fireEvent.change(screen.getByRole("textbox", { name: "配置草稿" }), {
      target: { value: "尚未保存" },
    });
    scrollY.mockReturnValue(180);
    fireEvent.mouseDown(screen.getByRole("tab", { name: "日志" }), { button: 0, ctrlKey: false });
    fireEvent.mouseDown(screen.getByRole("tab", { name: "总览" }), { button: 0, ctrlKey: false });
    expect(screen.getByRole("tabpanel")).toHaveAccessibleName("总览");
    expect(screen.getByRole("textbox", { name: "筛选群聊" })).toHaveValue("示例群");
    expect(scroll).toHaveBeenLastCalledWith({ top: 420, behavior: "instant" });
    fireEvent.mouseDown(screen.getByRole("tab", { name: "配置" }), { button: 0, ctrlKey: false });
    expect(screen.getByRole("textbox", { name: "配置草稿" })).toHaveValue("尚未保存");
    expect(scroll).toHaveBeenLastCalledWith({ top: 180, behavior: "instant" });
  });

  it("键盘切页后焦点保持在导航，可继续进入页面操作", async () => {
    vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    render(<Fixture />);
    const first = screen.getByRole("tab", { name: "总览" });
    act(() => first.focus());
    fireEvent.keyDown(first, { key: "ArrowRight" });
    await waitFor(() => expect(screen.getByRole("tab", { name: "配置" })).toHaveFocus());
    expect(screen.getByRole("tabpanel")).toHaveAccessibleName("配置");
    expect(screen.getByRole("button", { name: "发起分析" })).toBeEnabled();
    expect(screen.getByRole("link", { name: "跳到页面内容" })).toHaveAttribute(
      "href",
      "#page-content",
    );
  });
});
