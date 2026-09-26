import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusTag } from "../StatusTag";

describe("状态标签组件 (StatusTag Component)", () => {
  it("应当正确渲染成功状态标签 (succeeded)", () => {
    render(<StatusTag status="succeeded" />);
    expect(screen.getByText(/成功|完成|succeeded/i)).toBeInTheDocument();
  });

  it("应当正确渲染失败状态标签 (failed)", () => {
    render(<StatusTag status="failed" />);
    expect(screen.getByText(/失败|failed/i)).toBeInTheDocument();
  });

  it("应当正确渲染进行中状态标签 (running)", () => {
    render(<StatusTag status="running" />);
    expect(screen.getByText(/运行中|执行中|running/i)).toBeInTheDocument();
  });
});
