import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppShell } from "@/app/ui/AppShell";
import { usePageNavigation } from "@/app/model/usePageNavigation";

function Fixture({ configDirty = false }: { configDirty?: boolean }) {
  const { page, visited, navigate } = usePageNavigation("overview");
  return (
    <AppShell
      activePage={page}
      visited={visited}
      onNavigate={navigate}
      onRefresh={() => {}}
      onOpenTrigger={() => {}}
      loading={false}
      configDirty={configDirty}
      items={[
        { key: "overview", label: "总览", icon: null, children: <input aria-label="筛选群聊" /> },
        { key: "config", label: "配置", icon: null, children: <textarea aria-label="配置草稿" /> },
        { key: "logs", label: "日志", icon: null, children: <p>示例日志</p> },
      ]}
    />
  );
}

describe("正式页面导航", () => {
  it("未保存提醒跨页可见，返回配置不丢草稿且不重复展示，保存后消失", () => {
    vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    const view = render(<Fixture configDirty />);
    expect(screen.getByRole("status", { name: "配置未保存提醒" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "返回配置" }));
    expect(screen.getByRole("tabpanel")).toHaveAccessibleName("配置");
    expect(screen.queryByRole("status", { name: "配置未保存提醒" })).not.toBeInTheDocument();
    fireEvent.change(screen.getByRole("textbox", { name: "配置草稿" }), {
      target: { value: "未保存的草稿" },
    });
    fireEvent.mouseDown(screen.getByRole("tab", { name: "日志" }), { button: 0, ctrlKey: false });
    expect(screen.getByRole("status", { name: "配置未保存提醒" })).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "返回配置" }));
    expect(screen.getByRole("textbox", { name: "配置草稿" })).toHaveValue("未保存的草稿");
    fireEvent.mouseDown(screen.getByRole("tab", { name: "总览" }), { button: 0, ctrlKey: false });
    view.rerender(<Fixture />);
    expect(screen.queryByRole("status", { name: "配置未保存提醒" })).not.toBeInTheDocument();
  });

  afterEach(() => {
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it("选中项居中，快速切页取消旧帧，重按当前页或调整宽度都能重新定位", () => {
    const frames = new Map<number, FrameRequestCallback>();
    let sequence = 0;
    vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
      frames.set(++sequence, callback);
      return sequence;
    });
    vi.stubGlobal("cancelAnimationFrame", (id: number) => frames.delete(id));
    let resize: (() => void) | undefined;
    vi.stubGlobal(
      "ResizeObserver",
      class {
        constructor(callback: () => void) {
          resize = callback;
        }
        observe() {}
        disconnect() {}
      },
    );
    vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    const view = render(<Fixture />);
    expect(screen.getByRole("img", { name: "AstrBot 群分析总结插件" })).toBeVisible();
    const container = screen.getByRole("tablist", { name: "主导航" }).parentElement!;
    Object.defineProperties(container, {
      clientWidth: { configurable: true, value: 200 },
      scrollWidth: { configurable: true, value: 600 },
      scrollLeft: { configurable: true, writable: true, value: 100 },
    });
    const scroll = vi.fn();
    container.scrollTo = scroll;
    vi.spyOn(container, "getBoundingClientRect").mockReturnValue(new DOMRect(100, 0, 200, 32));
    const target = screen.getByRole("tab", { name: "日志" });
    Object.defineProperty(target, "offsetWidth", { configurable: true, value: 60 });
    vi.spyOn(target, "getBoundingClientRect").mockReturnValue(new DOMRect(350, 0, 60, 32));
    fireEvent.mouseDown(screen.getByRole("tab", { name: "配置" }), { button: 0 });
    fireEvent.mouseDown(target, { button: 0 });
    act(() => {
      const pending = [...frames.values()];
      frames.clear();
      pending.forEach((callback) => callback(0));
    });
    expect(scroll).toHaveBeenCalledTimes(1);
    expect(scroll).toHaveBeenLastCalledWith({ left: 280, behavior: "smooth" });
    frames.clear();
    vi.spyOn(window, "matchMedia").mockReturnValue({ ...window.matchMedia(""), matches: true });
    fireEvent.click(target);
    act(() => {
      const pending = [...frames.values()];
      frames.clear();
      pending.forEach((callback) => callback(0));
    });
    expect(scroll).toHaveBeenLastCalledWith({ left: 280, behavior: "auto" });
    frames.clear();
    resize?.();
    const resizeFrame = sequence;
    expect(frames.has(resizeFrame)).toBe(true);
    view.unmount();
    expect(frames.has(resizeFrame)).toBe(false);
  });

  it("纵向滚轮横移溢出导航，边界放行整页滚动，卸载后不再拦截", () => {
    const view = render(<Fixture />);
    const container = screen.getByRole("tablist", { name: "主导航" }).parentElement!;
    Object.defineProperties(container, {
      clientWidth: { configurable: true, value: 200 },
      scrollWidth: { configurable: true, value: 600 },
    });
    const wheel = new WheelEvent("wheel", { deltaY: 80, bubbles: true, cancelable: true });
    container.dispatchEvent(wheel);
    expect(wheel.defaultPrevented).toBe(true);
    expect(container.scrollLeft).toBe(80);
    for (const options of [
      { deltaX: 10 },
      { ctrlKey: true },
      { shiftKey: true },
      { metaKey: true },
    ]) {
      const event = new WheelEvent("wheel", { deltaY: 30, cancelable: true, ...options });
      container.dispatchEvent(event);
      expect(event.defaultPrevented).toBe(false);
    }
    container.scrollLeft = 400;
    const edge = new WheelEvent("wheel", { deltaY: 80, cancelable: true });
    container.dispatchEvent(edge);
    expect(edge.defaultPrevented).toBe(false);
    view.unmount();
    container.scrollLeft = 20;
    const removed = new WheelEvent("wheel", { deltaY: 80, cancelable: true });
    container.dispatchEvent(removed);
    expect(removed.defaultPrevented).toBe(false);
    expect(container.scrollLeft).toBe(20);
  });

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
