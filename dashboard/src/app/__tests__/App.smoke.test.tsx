import React from "react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { App } from "@/app/App";
import { toast } from "sonner";
import * as devBridge from "@/shared/api/devBridge";
import * as traceApi from "@/entities/trace/api/traceApi";
import * as taskApi from "@/entities/task/api/taskApi";
import * as configApi from "@/entities/config/api/configApi";

// 本测试验证页面装配和数据加载，不在 JSDOM 中运行 Canvas 动画。
vi.mock("echarts-for-react", () => ({ default: () => <div data-testid="chart" /> }));

describe("应用全局冒烟与集成测试 (App Smoke & Integration Test)", () => {
  it("真实配置草稿驱动跨页提醒，失败继续保护、保存或卸载后清理离开提醒", async () => {
    const scrollSpy = vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    const sseSpy = vi.spyOn(devBridge, "devSubscribeSSE").mockImplementation(() => () => {});
    const saveSpy = vi
      .spyOn(configApi, "savePluginConfig")
      .mockResolvedValueOnce({ success: false, message: "保存失败示例" })
      .mockResolvedValue({ success: true });
    const pending: Promise<unknown>[] = [];
    const originalGet = devBridge.devApiGet;
    const getSpy = vi.spyOn(devBridge, "devApiGet").mockImplementation(function <T>(
      path: string,
      params?: Record<string, unknown>,
    ) {
      const request = originalGet<T>(path, params);
      pending.push(request);
      return request;
    });
    const view = render(<App />);
    const leaving = () => {
      const event = new Event("beforeunload", { cancelable: true });
      window.dispatchEvent(event);
      return event.defaultPrevented;
    };
    try {
      expect(leaving()).toBe(false);
      fireEvent.mouseDown(screen.getByRole("tab", { name: "配置" }), { button: 0, ctrlKey: false });
      const days = await screen.findByRole("spinbutton", { name: "默认分析天数" });
      fireEvent.change(days, { target: { value: "3" } });
      expect(leaving()).toBe(true);
      fireEvent.mouseDown(screen.getByRole("tab", { name: "报告" }), { button: 0, ctrlKey: false });
      expect(screen.getByRole("status", { name: "配置未保存提醒" })).toBeVisible();
      fireEvent.click(screen.getByRole("button", { name: "返回配置" }));
      expect(days).toHaveValue(3);
      fireEvent.click(screen.getByRole("button", { name: "保存配置" }));
      await waitFor(() => expect(saveSpy).toHaveBeenCalledTimes(1));
      await screen.findByRole("alert");
      expect(leaving()).toBe(true);
      fireEvent.click(screen.getByRole("button", { name: "保存配置" }));
      await waitFor(() => expect(screen.getByText("没有未保存的修改")).toBeVisible());
      expect(leaving()).toBe(false);
      fireEvent.change(days, { target: { value: "4" } });
      expect(leaving()).toBe(true);
    } finally {
      view.unmount();
      expect(leaving()).toBe(false);
      await act(async () => {
        await Promise.allSettled(pending);
      });
      toast.dismiss();
      getSpy.mockRestore();
      saveSpy.mockRestore();
      sseSpy.mockRestore();
      scrollSpy.mockRestore();
    }
  }, 20000);

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
    const fetchConnectedPlatforms = taskApi.fetchConnectedPlatforms;
    const platformsSpy = vi
      .spyOn(taskApi, "fetchConnectedPlatforms")
      .mockImplementationOnce(fetchConnectedPlatforms)
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
      expect(screen.getByText("AstrBot 群分析总结插件")).toBeInTheDocument();

      // 验证核心导航 Tab 标签
      for (const name of ["总览", "分析记录", "统计", "报告", "配置", "数据", "日志"])
        expect(screen.getByRole("tab", { name })).toBeInTheDocument();

      // 等待实际数据，而不只检查初始页面已有的静态标题。
      await act(async () => {
        await Promise.allSettled(pending);
      });
      expect(screen.getByText("142")).toBeInTheDocument();
      const platformLabel = screen.getByText(/aiocqhttp_main · 987654321/);
      expect(platformLabel.parentElement?.querySelector("img")?.src).toContain("onebot.png");
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
      expect(platformsSpy).toHaveBeenCalledTimes(3);
      fireEvent.click(form.getByRole("button", { name: "取消" }));
      act(() => {
        toast.success("示例：任务已提交", { duration: Infinity });
      });
      // Sonner 先插入通知节点，再更新可见状态；找到文本不代表通知已经可见。
      await waitFor(() => expect(screen.getByText("示例：任务已提交")).toBeVisible());
      expect(screen.getByLabelText("操作通知（Alt+T）")).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "关闭提示" }));
      await waitFor(() => expect(screen.queryByText("示例：任务已提交")).not.toBeInTheDocument());
      for (const event of ["task_canceled", "task_timed_out", "task_finished"]) {
        cacheSpy.mockClear();
        act(() => receiveEvent?.({ parsed: { event, data: { task_id: "WEBUI-CANCEL" } } }));
        expect(cacheSpy).toHaveBeenCalledWith("WEBUI-CANCEL");
        await act(async () => {
          await Promise.allSettled(pending);
        });
      }
      fireEvent.mouseDown(screen.getByRole("tab", { name: "报告" }), { button: 0, ctrlKey: false });
      await screen.findByRole("list", { name: "报告文件" });
      const reportCalls = getSpy.mock.calls.filter(([path]) => path === "reports/history").length;
      act(() =>
        receiveEvent?.({ parsed: { event: "task_finished", data: { task_id: "ANOTHER-TASK" } } }),
      );
      await act(async () => {
        await Promise.allSettled(pending);
      });
      expect(getSpy.mock.calls.filter(([path]) => path === "reports/history")).toHaveLength(
        reportCalls,
      );
      expect(screen.getByText(/报告有更新/)).toBeVisible();
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
