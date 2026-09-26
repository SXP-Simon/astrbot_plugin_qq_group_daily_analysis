import React from "react";
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MetricCard } from "../MetricCard";

describe("KPI 指标卡片组件 (MetricCard Component)", () => {
  it("应当正确渲染标题、数值与单位后缀", () => {
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

  it("当提供副标题时应当完整展示副标题内容", () => {
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
