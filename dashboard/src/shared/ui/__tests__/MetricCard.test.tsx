import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricCard } from "../MetricCard";

describe("MetricCard Component", () => {
  it("should render title and formatted value", () => {
    render(
      <MetricCard
        title="今日分析请求"
        value={18}
        suffix="次"
      />
    );
    expect(screen.getByText("今日分析请求")).toBeInTheDocument();
    expect(screen.getByText("18")).toBeInTheDocument();
  });

  it("should render subTitle when provided", () => {
    render(
      <MetricCard
        title="成功率"
        value="95.1%"
        subTitle="覆盖 6 个群聊"
      />
    );
    expect(screen.getByText("成功率")).toBeInTheDocument();
    expect(screen.getByText("95.1%")).toBeInTheDocument();
    expect(screen.getByText("覆盖 6 个群聊")).toBeInTheDocument();
  });
});
