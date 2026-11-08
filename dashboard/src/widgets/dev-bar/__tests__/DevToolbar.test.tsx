import React from "react";
import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { DevToolbar } from "../DevToolbar";
import { mockSSEService } from "../../../mocks/sseMock";
import { toast } from "sonner";

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
