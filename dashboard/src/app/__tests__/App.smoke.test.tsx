import React from "react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { App } from "../App";
import { toast } from "sonner";
import * as devBridge from "../../shared/api/devBridge";
import * as traceApi from "../../entities/trace/api/traceApi";
import * as taskApi from "../../entities/task/api/taskApi";

// 本测试验证页面装配和数据加载，不在 JSDOM 中运行 Canvas 动画。
vi.mock("echarts-for-react", () => ({ default: () => <div data-testid="chart" /> }));

describe("应用全局冒烟与集成测试 (App Smoke & Integration Test)", () => {
  beforeEach(() => {
    localStorage.clear();
    delete (window as { AstrBotPluginPage?: unknown }).AstrBotPluginPage;
  });

  it("在独立开发环境下应当成功挂载根应用组件并正常渲染控制台导航与内容", async () => {
    // 冒烟测试只验证首次加载，不启动持续推送的演示计时器。
    let receiveEvent: Parameters<typeof devBridge.devSubscribeSSE>[0]["onMessage"] | undefined;
    const sseSpy = vi.spyOn(devBridge, "devSubscribeSSE").mockImplementation((handlers) => {
      receiveEvent = handlers.onMessage;
      return () => {};
    });
    const cacheSpy = vi.spyOn(traceApi, "invalidateTraceCache");
    const platformsSpy = vi
      .spyOn(taskApi, "fetchConnectedPlatforms")
      .mockRejectedValueOnce(new Error("连接失败"));
    const scrollSpy = vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    const pending: Promise<unknown>[] = [];
    const originalGet = devBridge.devApiGet;
    const getSpy = vi.spyOn(devBridge, "devApiGet").mockImplementation(function <T>(
      path: string,
      params?: Record<string, unknown>,
    ) {
      const result = originalGet<T>(path, params);
      pending.push(result);
      return result;
    });
    const view = render(<App />);
    try {
      // 验证顶部标题栏
      expect(screen.getByText("群聊分析")).toBeInTheDocument();

      // 验证核心导航 Tab 标签
      for (const name of ["总览", "分析记录", "统计", "报告", "配置", "数据", "日志"])
        expect(screen.getByRole("tab", { name })).toBeInTheDocument();

      // 等待实际数据，而不只检查初始页面已有的静态标题。
      await act(async () => {
        await Promise.allSettled(pending);
      });
      expect(screen.getByText("142")).toBeInTheDocument();
      fireEvent.click(screen.getAllByRole("button", { name: "发起分析" })[0]);
      const form = within(await screen.findByRole("dialog", { name: "发起分析" }));
      expect(await form.findByText("平台列表未能读取，可重试加载或使用默认选择。")).toBeVisible();
      fireEvent.change(form.getByLabelText("群号 / 会话标识"), { target: { value: "demo-retry" } });
      fireEvent.click(form.getByRole("button", { name: "重新加载选项" }));
      await act(async () => {
        await Promise.allSettled(pending);
      });
      expect(
        form.queryByText("平台列表未能读取，可重试加载或使用默认选择。"),
      ).not.toBeInTheDocument();
      expect(form.getByLabelText("群号 / 会话标识")).toHaveValue("demo-retry");
      expect(platformsSpy).toHaveBeenCalledTimes(2);
      fireEvent.click(form.getByRole("button", { name: "取消" }));
      act(() => {
        toast.success("示例：任务已提交", { duration: Infinity });
      });
      expect(await screen.findByText("示例：任务已提交")).toBeVisible();
      expect(screen.getByLabelText("操作通知（Alt+T）")).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "关闭提示" }));
      for (const event of ["task_canceled", "task_timed_out", "task_finished"]) {
        cacheSpy.mockClear();
        act(() => receiveEvent?.({ parsed: { event, data: { task_id: "WEBUI-CANCEL" } } }));
        expect(cacheSpy).toHaveBeenCalledWith("WEBUI-CANCEL");
        await act(async () => {
          await Promise.allSettled(pending);
        });
      }
      fireEvent.mouseDown(screen.getByRole("tab", { name: "日志" }), { button: 0, ctrlKey: false });
      expect(screen.getByRole("tabpanel")).toHaveAccessibleName("日志");
      await act(async () => {
        await Promise.allSettled(pending);
      });
      const activeQueries = () =>
        getSpy.mock.calls.filter(([path]) => path === "tasks/active").length;
      const beforeHiddenEvent = activeQueries();
      act(() =>
        receiveEvent?.({ parsed: { event: "task_finished", data: { task_id: "HIDDEN-TASK" } } }),
      );
      await act(async () => {
        await Promise.allSettled(pending);
      });
      expect(activeQueries()).toBe(beforeHiddenEvent);
      fireEvent.mouseDown(screen.getByRole("tab", { name: "总览" }), { button: 0, ctrlKey: false });
      expect(screen.getByRole("tabpanel")).toHaveAccessibleName("总览");
      await act(async () => {
        await Promise.allSettled(pending);
      });
      expect(activeQueries()).toBe(beforeHiddenEvent + 1);
    } finally {
      toast.dismiss();
      view.unmount();
      // 等待初始化引出的详情请求收尾，避免回调落到已销毁的测试环境。
      await act(async () => {
        await Promise.allSettled(pending);
      });
      getSpy.mockRestore();
      sseSpy.mockRestore();
      cacheSpy.mockRestore();
      platformsSpy.mockRestore();
      scrollSpy.mockRestore();
    }
  }, 20000);
});
