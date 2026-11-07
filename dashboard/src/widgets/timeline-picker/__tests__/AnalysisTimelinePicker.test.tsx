import { useState } from "react";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import type { TraceRecord } from "../../../entities/trace/model/types";
import { AnalysisTimelinePicker } from "../AnalysisTimelinePicker";

const traces: TraceRecord[] = ["a", "b", "c"].map((id, index) => ({
  trace_id: `example-${id}`,
  group_name: `示例 ${id}`,
  group_id: "123",
  platform: index === 0 ? "telegram" : "discord",
  trigger_type: "manual",
  status: index === 0 ? "cancelled" : "succeeded",
  started_at: 300 - index * 100,
  ...(index === 0 ? { total_tokens: 0, duration_ms: 0, compression_ratio: 0 } : {}),
}));
const onView = vi.fn();
function Picker() {
  const [selected, select] = useState(traces[0]);
  return (
    <AnalysisTimelinePicker
      traces={traces}
      selectedTrace={selected}
      onSelectTrace={select}
      onViewTraceDetail={onView}
    />
  );
}
const frames = new Map<number, FrameRequestCallback>();
let sequence = 0;
beforeEach(() => {
  frames.clear();
  sequence = 0;
  vi.spyOn(window, "requestAnimationFrame").mockImplementation((callback) => {
    frames.set(++sequence, callback);
    return sequence;
  });
  vi.spyOn(window, "cancelAnimationFrame").mockImplementation((id) => {
    frames.delete(id);
  });
});
afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

it("键盘方向键与首尾键切换任务并保持焦点，前后按钮和详情对应当前选择", () => {
  render(<Picker />);
  const first = screen.getByRole("button", { name: /选择任务 示例 a/ });
  const second = screen.getByRole("button", { name: /选择任务 示例 b/ });
  const last = screen.getByRole("button", { name: /选择任务 示例 c/ });
  expect(screen.getByRole("button", { name: "上一条" })).toBeDisabled();
  first.focus();
  fireEvent.keyDown(first, { key: "ArrowRight" });
  expect(second).toHaveFocus();
  expect(second).toHaveAttribute("aria-pressed", "true");
  expect(first).toHaveAttribute("tabindex", "-1");
  fireEvent.keyDown(second, { key: "End" });
  expect(last).toHaveFocus();
  expect(screen.getByRole("button", { name: "下一条" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "查看所选任务" }));
  expect(onView).toHaveBeenCalledWith("example-c");
  fireEvent.keyDown(last, { key: "Home" });
  expect(first).toHaveFocus();
  fireEvent.click(screen.getByRole("button", { name: "下一条" }));
  expect(second).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(screen.getByRole("button", { name: "上一条" }));
  expect(first).toHaveAttribute("aria-pressed", "true");
});

it("状态、平台、用量、耗时与留存无需悬停，取消不冒充运行，零与缺失分开", () => {
  const view = render(<Picker />);
  const first = screen.getByRole("button", { name: /选择任务 示例 a/ });
  expect(within(first).getByText("已中止")).toBeVisible();
  expect(within(first).getByText("telegram · 123")).toBeVisible();
  expect(first).toHaveTextContent("Tokens 0 · 耗时 0ms");
  expect(first).toHaveTextContent("消息留存 0%");
  const second = screen.getByRole("button", { name: /选择任务 示例 b/ });
  expect(second).toHaveTextContent("Tokens 未记录 · 耗时 未记录");
  expect(second).toHaveTextContent("消息留存 未记录");
  view.rerender(
    <AnalysisTimelinePicker traces={traces} selectedTrace={null} onSelectTrace={vi.fn()} loading />,
  );
  expect(screen.getByRole("button", { name: /选择任务 示例 a/ })).toBeDisabled();
  expect(screen.getByRole("button", { name: "下一条" })).toBeDisabled();
});

it("快速切换取消旧帧，减少动态效果时直接定位，卸载取消待执行滚动", () => {
  vi.stubGlobal("matchMedia", vi.fn().mockReturnValue({ matches: true }));
  const view = render(<Picker />);
  const first = screen.getByRole("button", { name: /选择任务 示例 a/ });
  const last = screen.getByRole("button", { name: /选择任务 示例 c/ });
  const container = first.closest("ol")!.parentElement!;
  const scrollTo = vi.fn();
  Object.defineProperties(container, {
    scrollTo: { value: scrollTo },
    scrollWidth: { value: 900 },
    clientWidth: { value: 300 },
  });
  Object.defineProperties(last, { offsetLeft: { value: 500 }, offsetWidth: { value: 240 } });
  fireEvent.keyDown(first, { key: "ArrowRight" });
  fireEvent.keyDown(screen.getByRole("button", { name: /选择任务 示例 b/ }), { key: "End" });
  expect(frames.size).toBe(1);
  act(() => {
    for (const callback of frames.values()) callback(0);
    frames.clear();
  });
  expect(scrollTo).toHaveBeenCalledTimes(1);
  expect(scrollTo).toHaveBeenCalledWith({ left: 470, behavior: "auto" });
  fireEvent.keyDown(last, { key: "Home" });
  expect(frames.size).toBe(1);
  view.unmount();
  expect(frames.size).toBe(0);
});

it("鼠标拖动只平移不误选，键盘激活仍可选择；触屏保留原生滑动", () => {
  vi.stubGlobal("PointerEvent", MouseEvent);
  render(<Picker />);
  const first = screen.getByRole("button", { name: /选择任务 示例 a/ });
  const last = screen.getByRole("button", { name: /选择任务 示例 c/ });
  const container = first.closest("ol")!.parentElement!;
  const down = new MouseEvent("pointerdown", { bubbles: true, clientX: 100, button: 0 });
  Object.defineProperty(down, "pointerType", { value: "mouse" });
  fireEvent(container, down);
  fireEvent.pointerMove(container, { clientX: 30 });
  fireEvent.pointerUp(container);
  expect(container.scrollLeft).toBe(70);
  fireEvent.click(last, { detail: 1 });
  expect(first).toHaveAttribute("aria-pressed", "true");
  fireEvent.click(last, { detail: 0 });
  expect(last).toHaveAttribute("aria-pressed", "true");
  const touch = new MouseEvent("pointerdown", { bubbles: true, clientX: 100 });
  Object.defineProperty(touch, "pointerType", { value: "touch" });
  fireEvent(container, touch);
  fireEvent.pointerMove(container, { clientX: 10 });
  expect(container.scrollLeft).toBe(70);
});
