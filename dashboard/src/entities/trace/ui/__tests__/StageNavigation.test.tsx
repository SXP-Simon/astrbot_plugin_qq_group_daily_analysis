import { fireEvent, render, screen, within } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { SpanTimeline } from "../SpanTimeline";
import type { TraceSpan } from "../../model/types";

const first: TraceSpan = {
  trace_id: "recovered",
  span_id: "first",
  stage_name: "FETCH_MESSAGES",
  started_at: 1,
  status: "success",
  duration_ms: 200,
  payload: {},
};
const renderSpan: TraceSpan = {
  ...first,
  span_id: "render",
  stage_name: "RENDER_REPORT",
  payload: { render_attempts: [{ status: "failed", error: "首次超时" }, { status: "success" }] },
};

it("警告阶段选中与取消选中均保留警告状态，耗时条不改变统计含义", () => {
  render(
    <SpanTimeline
      spans={[first, { ...renderSpan, status: "warning", payload: { warning: "请求限流" } }]}
      taskStatus="succeeded"
      totalDurationMs={1000}
    />,
  );
  const tree = within(screen.getByRole("navigation", { name: "执行阶段" }));
  const warning = tree.getByRole("button", { name: /报告长图渲染与生成/ });
  expect(warning).toHaveAttribute("data-outcome", "warning");
  expect(warning).toHaveAttribute("aria-current", "true");
  expect(within(warning).getByText("警告 (200ms)")).toHaveClass("stage-status");
  expect(warning).toHaveTextContent("占总耗时 20%");
  fireEvent.click(tree.getByRole("button", { name: /拉取聊天记录/ }));
  expect(warning).not.toHaveAttribute("data-selected");
  expect(warning).toHaveAttribute("data-outcome", "warning");
});

it("任务完成后默认定位渲染恢复阶段，并保留最终完成状态", () => {
  const view = render(<SpanTimeline spans={[first, renderSpan]} taskStatus="succeeded" />);
  const tree = within(screen.getByRole("navigation", { name: "执行阶段" }));
  expect(tree.getByRole("button", { name: /报告长图渲染与生成/ })).toHaveAttribute(
    "aria-current",
    "true",
  );
  expect(tree.getByText("后续渲染已成功")).toBeVisible();
  expect(
    within(screen.getByLabelText("阶段提示")).getByText("此前失败原因：首次超时"),
  ).toBeVisible();
  expect(tree.getAllByText("完成 (200ms)")).toHaveLength(2);
  fireEvent.click(tree.getByRole("button", { name: /拉取聊天记录/ }));
  view.rerender(<SpanTimeline spans={[{ ...first }, { ...renderSpan }]} taskStatus="succeeded" />);
  expect(tree.getByRole("button", { name: /拉取聊天记录/ })).toHaveAttribute(
    "aria-current",
    "true",
  );
});

it("当前执行和真正失败的阶段优先于已有恢复提示", () => {
  const current = {
    ...first,
    span_id: "current",
    stage_name: "DISPATCH_REPORT",
    status: "running",
  };
  const view = render(<SpanTimeline spans={[first, renderSpan, current]} taskStatus="running" />);
  const tree = within(screen.getByRole("navigation", { name: "执行阶段" }));
  expect(tree.getByRole("button", { name: /分发|发送/ })).toHaveAttribute("aria-current", "true");
  view.rerender(
    <SpanTimeline
      spans={[first, renderSpan, { ...current, status: "failed", payload: { error: "发送失败" } }]}
      taskStatus="failed"
    />,
  );
  expect(tree.getByRole("button", { name: /分发|发送/ })).toHaveAttribute("aria-current", "true");
  expect(screen.getByText("发送失败")).toBeVisible();
});

it("窄容器选择阶段后定位证据，返回按钮恢复阶段焦点", () => {
  const scroll = vi.fn();
  const original = HTMLElement.prototype.scrollIntoView;
  HTMLElement.prototype.scrollIntoView = scroll;
  try {
    const { container } = render(
      <SpanTimeline spans={[first, renderSpan]} taskStatus="succeeded" />,
    );
    Object.defineProperty(container.querySelector(".stage-inspection"), "clientWidth", {
      configurable: true,
      value: 390,
    });
    const button = within(screen.getByRole("navigation", { name: "执行阶段" })).getByRole(
      "button",
      { name: /拉取聊天记录/ },
    );
    fireEvent.click(button);
    expect(screen.getByRole("heading", { name: /阶段详情/ })).toHaveFocus();
    expect(scroll).toHaveBeenCalledWith({ block: "start" });
    fireEvent.click(screen.getByRole("button", { name: "返回阶段列表" }));
    expect(button).toHaveFocus();
    expect(scroll).toHaveBeenLastCalledWith({ block: "nearest" });
  } finally {
    HTMLElement.prototype.scrollIntoView = original;
  }
});
