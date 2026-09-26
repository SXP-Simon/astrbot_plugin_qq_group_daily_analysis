import React from "react";
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { App } from "../App";

describe("App Smoke & Integration Test", () => {
  beforeEach(() => {
    localStorage.clear();
    delete (window as { AstrBotPluginPage?: unknown }).AstrBotPluginPage;
  });

  it("should mount App successfully without crashing and display dashboard tabs", async () => {
    render(<App />);

    // Check HeaderBar presence
    expect(screen.getByText(/QQ群日常分析控制台/i)).toBeInTheDocument();

    // Check Tabs presence
    expect(screen.getByText(/运行总览/i)).toBeInTheDocument();
    expect(screen.getAllByText(/分析记录/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/历史报告/i)).toBeInTheDocument();
    expect(screen.getByText(/运行日志/i)).toBeInTheDocument();
    expect(screen.getByText(/配置中心/i)).toBeInTheDocument();

    // Wait for Mock metrics summary to populate
    await waitFor(
      () => {
        expect(screen.getByText(/今日分析次数/i)).toBeInTheDocument();
        expect(screen.getByText(/历史总运行/i)).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });
});
