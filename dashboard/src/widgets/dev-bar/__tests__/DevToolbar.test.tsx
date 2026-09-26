import React from "react";
import { describe, it, expect, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { DevToolbar } from "../DevToolbar";

describe("DevToolbar Component", () => {
  beforeEach(() => {
    localStorage.clear();
    delete (window as { AstrBotPluginPage?: unknown }).AstrBotPluginPage;
  });

  it("should render developer toolbar in dev standalone mode", () => {
    render(<DevToolbar />);
    expect(screen.getByText(/DEV:/i)).toBeInTheDocument();
    expect(screen.getByText("开发工具箱")).toBeInTheDocument();
  });
});
