import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { StageMetricsBadges } from "../StageMetricsBadges";
import { TaskStageBadge } from "../../../task/ui/TaskStageBadge";

vi.mock("../../../../shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));

it("区分编译进程峰值与宿主内存，隐藏非法遥测并提示预算耗尽", () => {
  render(<StageMetricsBadges stageName="TYPST_COMPILE" payload={{ worker_peak_rss_mb: 156.9, delta_memory_mb: 1.2, font_setup_ms: Number.NaN, network_budget_exhausted: true }} />);
  expect(screen.getByText("编译进程峰值:")).toBeVisible();
  expect(screen.getByText("156.9 MiB")).toBeVisible();
  expect(screen.getByText("宿主 RSS 变化:")).toBeVisible();
  expect(screen.queryByText("字体初始化:")).not.toBeInTheDocument();
  expect(screen.getByText("已耗尽，保留正文")).toBeVisible();
});

it("活跃任务显示可读的Typst阶段", () => {
  render(<TaskStageBadge stage="TYPST_RESOURCES" />);
  expect(screen.getByText("Typst 本地素材与下载")).toBeVisible();
});
