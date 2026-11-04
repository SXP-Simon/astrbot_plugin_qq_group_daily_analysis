import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { StageMetricsBadges } from "../StageMetricsBadges";
import { TaskStageBadge } from "../../../task/ui/TaskStageBadge";

vi.mock("../../../../shared/lib/useTheme", () => ({ useTheme: () => ({ isDark: false }) }));

it("本地编译隐藏旧海外标签，并标出终止前的实际执行阶段", () => {
  render(<StageMetricsBadges stageName="IMAGE_RENDER_ATTEMPT" payload={{ service_type: "typst", resource_environment: "Overseas", execution_location: "本地隔离进程", worker_phase: "raster", worker_metrics_partial: true }} />);
  expect(screen.queryByText("Overseas")).not.toBeInTheDocument();
  expect(screen.getByText("本地隔离进程")).toBeVisible();
  expect(screen.getByText("栅格导出")).toBeVisible();
  expect(screen.getByText(/指标为进程终止前的采样/)).toBeVisible();
});

it("报告父阶段同时明确展示 Typst 编译增长和独立的宿主净变化", () => {
  render(<StageMetricsBadges stageName="RENDER_REPORT" payload={{ typst_peak_rss_mb: 250, typst_peak_delta_mb: 220, typst_rss_source: "linux_proc_status", delta_memory_mb: 0.1 }} />);
  expect(screen.getByText("Typst 子进程 RSS 峰值:")).toBeVisible();
  expect(screen.getByText("250 MiB")).toBeVisible();
  expect(screen.getByText("Typst 编译峰值增长:")).toBeVisible();
  expect(screen.getByText("220 MiB")).toBeVisible();
  expect(screen.getByText("宿主 RSS 净变化:")).toBeVisible();
});

it("区分编译进程峰值与宿主内存，隐藏非法遥测并提示预算耗尽", () => {
  render(<StageMetricsBadges stageName="TYPST_COMPILE" payload={{ worker_peak_rss_mb: 156.9, worker_start_rss_mb: 11.7, worker_peak_delta_mb: 145.2, worker_rss_source: "linux_proc_status", delta_memory_mb: 0, font_setup_ms: Number.NaN, network_budget_exhausted: true }} />);
  expect(screen.getByText("子进程 RSS 峰值:")).toBeVisible();
  expect(screen.getByText("156.9 MiB")).toBeVisible();
  expect(screen.getByText("宿主 RSS 净变化:")).toBeVisible();
  expect(screen.getByText("0.0 MiB")).toBeVisible();
  expect(screen.getByText("145.2 MiB")).toBeVisible();
  expect(screen.getByText("子进程启动 RSS:")).toBeVisible();
  expect(screen.getByText("编译峰值增长:")).toBeVisible();
  expect(screen.getByText("宿主净变化不含隔离编译开销；子进程结束后释放内存。")).toBeVisible();
  expect(screen.queryByText("字体初始化:")).not.toBeInTheDocument();
  expect(screen.getByText("已耗尽，保留正文")).toBeVisible();
});

it("旧口径峰值明确标记，非法宿主 RSS 不展示为 NaN", () => {
  render(<StageMetricsBadges stageName="TYPST_COMPILE" payload={{ worker_peak_rss_mb: 2096, delta_memory_mb: Number.NaN }} />);
  expect(screen.getByText("进程历史 RSS 峰值:")).toBeVisible();
  expect(screen.queryByText("子进程 RSS 峰值:")).not.toBeInTheDocument();
  expect(screen.queryByText("宿主 RSS 净变化:")).not.toBeInTheDocument();
  expect(screen.getByText("历史采集口径可能包含启动时继承的内存，不能直接作为本次编译占用。")).toBeVisible();
});

it("活跃任务显示可读的Typst阶段", () => {
  render(<TaskStageBadge stage="TYPST_RESOURCES" />);
  expect(screen.getByText("Typst 本地素材与下载")).toBeVisible();
});


it("长图降档同时展示请求与实际密度，说明固定排版未改变", () => {
  render(<StageMetricsBadges stageName="TYPST_COMPILE" payload={{ requested_raster_ppi: 216, raster_ppi: 180 }} />);
  expect(screen.getByText("216 PPI")).toBeVisible();
  expect(screen.getByText("180 PPI")).toBeVisible();
  expect(screen.getByText("长图像素预算已限制导出密度，排版与内容保持不变。")).toBeVisible();
});


it("显示实际标题字体，便于检查全瀨體是否加载或回退", () => {
  render(<StageMetricsBadges stageName="TYPST_RESOURCES" payload={{ title_font: "cjkFonts" }} />);
  expect(screen.getByText("标题字体:")).toBeVisible();
  expect(screen.getByText("cjkFonts")).toBeVisible();
});
