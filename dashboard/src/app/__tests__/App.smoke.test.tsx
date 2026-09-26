import React from "react";
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { App } from "../App";

describe("应用全局冒烟与集成测试 (App Smoke & Integration Test)", () => {
  beforeEach(() => {
    localStorage.clear();
    delete (window as { AstrBotPluginPage?: unknown }).AstrBotPluginPage;
  });

  it("在独立开发环境下应当成功挂载根应用组件并正常渲染控制台导航与内容", async () => {
    render(<App />);

    // 验证顶部标题栏
    expect(screen.getByText(/QQ群日常分析控制台/i)).toBeInTheDocument();

    // 验证核心导航 Tab 标签
    expect(screen.getByText(/运行总览/i)).toBeInTheDocument();
    expect(screen.getAllByText(/分析记录/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/历史报告/i)).toBeInTheDocument();
    expect(screen.getByText(/运行日志/i)).toBeInTheDocument();
    expect(screen.getByText(/配置中心/i)).toBeInTheDocument();

    // 等待 Mock 大盘指标数据异步加载完成
    await waitFor(
      () => {
        expect(screen.getByText(/今日分析次数/i)).toBeInTheDocument();
        expect(screen.getByText(/历史总运行/i)).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });
});
