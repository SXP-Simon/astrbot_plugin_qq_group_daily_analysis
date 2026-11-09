import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DevToolbar } from "@/widgets/dev-bar/DevToolbar";
import { mockSSEService } from "@/mocks/sseMock";
import { toast } from "sonner";
import { getDevThemeContext } from "@/shared/api/devThemeContext";

vi.mock("sonner", () => ({ toast: { success: vi.fn(), info: vi.fn() } }));

describe("开发者工具悬浮栏组件 (DevToolbar Component)", () => {
  beforeEach(() => {
    localStorage.clear();
    window.history.replaceState(null, "", "/?devMode=mock");
    delete (window as { AstrBotPluginPage?: unknown }).AstrBotPluginPage;
  });

  afterEach(() => vi.restoreAllMocks());

  it("在本地独立开发模式下应当正确挂载并渲染开发工具栏", () => {
    render(<DevToolbar />);
    expect(screen.getByText(/DEV:/i)).toBeInTheDocument();
    expect(screen.getByText("开发工具箱")).toBeInTheDocument();
  });

  it("工具弹窗可通过 Escape 关闭并返回入口焦点，注入使用已有示例任务", async () => {
    const emit = vi.spyOn(mockSSEService, "emitTaskHeartbeat").mockReturnValue(true);
    render(<DevToolbar />);
    const trigger = screen.getByRole("button", { name: "开发工具箱" });
    trigger.focus();
    fireEvent.click(trigger);
    expect(screen.getByRole("dialog", { name: "开发工具箱" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "通信模式" })).toHaveValue("mock");
    fireEvent.click(screen.getByRole("button", { name: "注入测试 SSE 任务事件" }));
    expect(emit).toHaveBeenCalledOnce();
    expect(toast.success).toHaveBeenCalledWith("已更新一个示例任务及其日志");
    fireEvent.keyDown(document.activeElement || document.body, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("没有活跃示例时提示结果，代理模式禁用示例注入", () => {
    const emit = vi.spyOn(mockSSEService, "emitTaskHeartbeat").mockReturnValue(false);
    const view = render(<DevToolbar />);
    fireEvent.click(screen.getByRole("button", { name: "开发工具箱" }));
    fireEvent.click(screen.getByRole("button", { name: "注入测试 SSE 任务事件" }));
    expect(toast.info).toHaveBeenCalledWith("没有运行中的示例任务，请先发起分析");
    view.unmount();
    window.history.replaceState(null, "", "/?devMode=proxy");
    render(<DevToolbar />);
    fireEvent.click(screen.getByRole("button", { name: "开发工具箱" }));
    expect(screen.getByRole("button", { name: "注入测试 SSE 任务事件" })).toBeDisabled();
    expect(emit).toHaveBeenCalledOnce();
  });

  it("AstrBot 宿主环境不显示开发工具入口", () => {
    Object.defineProperty(window, "AstrBotPluginPage", { configurable: true, value: {} });
    render(<DevToolbar />);
    expect(screen.queryByRole("button", { name: "开发工具箱" })).not.toBeInTheDocument();
    delete (window as { AstrBotPluginPage?: unknown }).AstrBotPluginPage;
  });
});

it("自定义配色开关、颜色输入和恢复默认同步更新开发上下文", () => {
  localStorage.clear();
  document.documentElement.style.setProperty("--default-primary", "#aff33e");
  document.documentElement.style.setProperty("--default-secondary", "#4b9994");
  delete window.AstrBotPluginPage;
  render(<DevToolbar />);
  fireEvent.click(screen.getByRole("button", { name: "开发工具箱" }));
  const toggle = screen.getByRole("switch", { name: "模拟宿主自定义配色" });
  expect(screen.getByLabelText("主色")).toBeDisabled();
  fireEvent.click(toggle);
  expect(getDevThemeContext().themeColors).toEqual({ primary: "#aff33e", secondary: "#4b9994" });
  fireEvent.change(screen.getByLabelText("主色"), { target: { value: "#123456" } });
  fireEvent.change(screen.getByLabelText("辅助色"), { target: { value: "#abcdef" } });
  expect(getDevThemeContext().themeColors).toEqual({ primary: "#123456", secondary: "#abcdef" });
  fireEvent.click(screen.getByRole("button", { name: "切换亮色 / 暗黑主题" }));
  expect(getDevThemeContext().themeColors?.primary).toBe("#123456");
  fireEvent.click(screen.getByRole("button", { name: "恢复插件默认配色" }));
  expect(getDevThemeContext().themeColors).toEqual({ primary: "#aff33e", secondary: "#4b9994" });
  expect(toggle).toBeChecked();
  expect(screen.getByLabelText("主色")).toBeEnabled();
  expect(screen.getByLabelText("主色")).toHaveValue("#aff33e");
  fireEvent.change(screen.getByLabelText("主色"), { target: { value: "#abcdef" } });
  fireEvent.click(toggle);
  expect(getDevThemeContext().themeColors).toBeUndefined();
  expect(screen.getByRole("button", { name: "恢复插件默认配色" })).toBeEnabled();
  fireEvent.click(screen.getByRole("button", { name: "恢复插件默认配色" }));
  expect(toggle).not.toBeChecked();
  expect(getDevThemeContext().themeColors).toBeUndefined();
  expect(screen.getByLabelText("主色")).toHaveValue("#aff33e");
});
