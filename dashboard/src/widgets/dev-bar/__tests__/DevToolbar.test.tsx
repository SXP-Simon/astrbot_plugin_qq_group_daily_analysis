import React from "react";
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { DevToolbar } from "../DevToolbar";

describe("开发者工具悬浮栏组件 (DevToolbar Component)", () => {
  beforeEach(() => {
    localStorage.clear();
    delete (window as { AstrBotPluginPage?: unknown }).AstrBotPluginPage;
  });

  it("在本地独立开发模式下应当正确挂载并渲染开发工具栏", () => {
    render(<DevToolbar />);
    expect(screen.getByText(/DEV:/i)).toBeInTheDocument();
    expect(screen.getByText("开发工具箱")).toBeInTheDocument();
  });
});
