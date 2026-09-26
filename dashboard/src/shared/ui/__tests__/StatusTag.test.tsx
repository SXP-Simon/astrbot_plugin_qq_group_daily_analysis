import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusTag } from "../StatusTag";

describe("StatusTag Component", () => {
  it("should render succeeded status tag", () => {
    render(<StatusTag status="succeeded" />);
    expect(screen.getByText(/成功|完成|succeeded/i)).toBeInTheDocument();
  });

  it("should render failed status tag", () => {
    render(<StatusTag status="failed" />);
    expect(screen.getByText(/失败|failed/i)).toBeInTheDocument();
  });

  it("should render running status tag", () => {
    render(<StatusTag status="running" />);
    expect(screen.getByText(/运行中|执行中|running/i)).toBeInTheDocument();
  });
});
