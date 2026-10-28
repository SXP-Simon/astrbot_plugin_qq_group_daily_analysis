import React from "react";
import { describe, it, expect, beforeEach, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { App } from "../App";
import * as devBridge from "../../shared/api/devBridge";

// 本测试验证页面装配和数据加载，不在 JSDOM 中运行 Canvas 动画。
vi.mock("echarts-for-react", () => ({ default: () => <div data-testid="chart" /> }));

describe("应用全局冒烟与集成测试 (App Smoke & Integration Test)", () => {
  beforeEach(() => {
    localStorage.clear();
    delete (window as { AstrBotPluginPage?: unknown }).AstrBotPluginPage;
  });

  it("在独立开发环境下应当成功挂载根应用组件并正常渲染控制台导航与内容", async () => {
    // 冒烟测试只验证首次加载，不启动持续推送的演示计时器。
    const sseSpy = vi.spyOn(devBridge, "devSubscribeSSE").mockReturnValue(() => {});
    const pending: Promise<unknown>[] = [];
    const originalGet = devBridge.devApiGet;
    const getSpy = vi.spyOn(devBridge, "devApiGet").mockImplementation(function<T>(path: string, params?: Record<string, unknown>) {
      const result = originalGet<T>(path, params);
      pending.push(result);
      return result;
    });
    const view = render(<App />);
    try {

      // 验证顶部标题栏
      expect(screen.getByText(/群分析插件控制台/i)).toBeInTheDocument();

      // 验证核心导航 Tab 标签
      expect(screen.getByText(/运行总览/i)).toBeInTheDocument();
      expect(screen.getAllByText(/分析记录/i).length).toBeGreaterThan(0);
      expect(screen.getByText(/历史报告/i)).toBeInTheDocument();
      expect(screen.getByText(/运行日志/i)).toBeInTheDocument();
      expect(screen.getByText(/配置中心/i)).toBeInTheDocument();

      // 等待实际数据，而不只检查初始页面已有的静态标题。
      await act(async () => { await Promise.allSettled(pending); });
      expect(screen.getByText("142")).toBeInTheDocument();
    } finally {
      view.unmount();
      // 等待初始化引出的详情请求收尾，避免回调落到已销毁的测试环境。
      await act(async () => { await Promise.allSettled(pending); });
      getSpy.mockRestore();
      sseSpy.mockRestore();
    }
  }, 20000);
});
