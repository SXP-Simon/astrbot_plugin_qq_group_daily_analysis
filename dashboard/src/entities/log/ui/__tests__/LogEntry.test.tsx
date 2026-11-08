import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { LogEntry } from "../LogEntry";
import type { PluginLogItem } from "../../model/types";

const log: PluginLogItem = {
  id: "log-example",
  timestamp: 1,
  time_str: "12:00:00.001",
  level: "INFO",
  logger_name: "Render",
  tag: "Render",
  location: "render.py:12",
  function_name: "Renderer.generate",
  message: "示例正文\n下一行",
  raw: "原始日志",
  trace_id: "trace-example",
  stage: "RENDER_REPORT",
};

it.each([
  ["DEBUG", "bg-creative/15", "border-l-transparent"],
  ["INFO", "bg-info/15", "border-l-transparent"],
  ["WARNING", "bg-warning/15", "border-l-warning"],
  ["ERROR", "bg-destructive/15", "border-l-destructive"],
  ["CRITICAL", "bg-destructive", "border-l-destructive"],
] as const)("%s 使用同一套等级提示色，保留来源、模块和多行正文", (level, badge, border) => {
  const { container } = render(<LogEntry item={{ ...log, level }} />);
  expect(screen.getByText(level)).toHaveClass(badge);
  expect(container.firstElementChild).toHaveClass(border);
  expect(screen.getByTitle("Render")).toHaveTextContent("报告与模板");
  expect(screen.getByTitle("日志调用位置")).toHaveTextContent("render.py:12 Renderer.generate()");
  expect(screen.getByText(/示例正文/)).toHaveClass("whitespace-pre-wrap");
  expect(screen.queryByRole("button")).not.toBeInTheDocument();
});

it("日志页可关联任务，详情可省略重复入口，未知模块和缺失来源仍能显示", () => {
  const open = vi.fn();
  const view = render(<LogEntry item={log} onViewTrace={open} />);
  fireEvent.click(screen.getByRole("button", { name: "查看任务 trace-example" }));
  expect(open).toHaveBeenCalledWith("trace-example");
  view.rerender(
    <LogEntry item={{ ...log, tag: "Extension", location: null, function_name: null }} />,
  );
  expect(screen.getByTitle("Extension")).toHaveTextContent("Extension");
  expect(screen.getByTitle("日志调用位置")).toHaveTextContent("[Render]");
});
