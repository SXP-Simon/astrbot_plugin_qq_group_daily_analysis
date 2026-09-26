import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TraceSummaryCard } from "../../widgets/trace-drawer/ui/TraceSummaryCard";
import { TraceDrawer } from "../../widgets/trace-drawer/TraceDrawer";
import { ActiveTaskBoard } from "../../widgets/active-task-board/ActiveTaskBoard";
import { mockTraces } from "../data/traces";
import { mockActiveTasks } from "../data/tasks";
import { mockPluginLogs } from "../data/logs";

describe("UI 拟真数据矩阵与排版弹性测试 (UI Resilience & Layout Stress Tests)", () => {
  const dummyPreview = vi.fn();
  const dummyDownload = vi.fn();

  it("稠密重载场景：长文本群名、多产物平铺、超大 Token 与消耗应稳定渲染且不溢出崩溃", () => {
    const denseTrace = mockTraces.find((t) => t.trace_id === "trace-20260926-002-dense");
    expect(denseTrace).toBeDefined();
    if (!denseTrace) return;

    render(
      <TraceSummaryCard
        trace={denseTrace}
        onPreviewFile={dummyPreview}
        onDownloadFile={dummyDownload}
      />
    );

    // 验证超长群名与群号存在
    expect(screen.getByText(/2026 深度学习与自然语言处理前沿学术讨论/i)).toBeInTheDocument();
    expect(screen.getAllByText(/8899001122/).length).toBeGreaterThan(0);

    // 验证多格式产物文件平铺（PNG/Comic/HTML/JSON）
    expect(screen.getByText(/daily_analysis_8899001122_20260926\.png/i)).toBeInTheDocument();
    expect(screen.getByText(/comic_8899001122_20260926\.png/i)).toBeInTheDocument();
    expect(screen.getByText(/interactive_report_8899001122_20260926\.html/i)).toBeInTheDocument();
    expect(screen.getByText(/metadata_checkpoint_8899001122\.json/i)).toBeInTheDocument();
  });

  it("极简轻量场景：消息量过少跳过执行、0 Token、零开销应优雅展示且无除零或空指针异常", () => {
    const sparseTrace = mockTraces.find((t) => t.trace_id === "trace-20260926-003-sparse");
    expect(sparseTrace).toBeDefined();
    if (!sparseTrace) return;

    render(
      <TraceSummaryCard
        trace={sparseTrace}
        onPreviewFile={dummyPreview}
        onDownloadFile={dummyDownload}
      />
    );

    expect(screen.getByText("测试群")).toBeInTheDocument();
    expect(screen.getAllByText(/556677/).length).toBeGreaterThan(0);
    expect(screen.getByText("320ms")).toBeInTheDocument();
    expect(screen.getByText("8 条")).toBeInTheDocument();
  });

  it("超时中断与抽屉异常渲染：多行 Python Traceback 堆栈与错误阶段应清晰展示", async () => {
    render(
      <TraceDrawer
        open={true}
        traceId="trace-20260926-004-timeout"
        onClose={vi.fn()}
      />
    );

    // 验证抽屉内异步加载后渲染的错误阶段与异常详情
    expect(await screen.findByText(/在【大模型分析】阶段发生异常/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Connection timeout to api\.openai\.com/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/查看异常堆栈/i)).toBeInTheDocument();
  });

  it("降级告警场景：多平台 Telegram 渠道与群名应正常展现", () => {
    const tgWarningTrace = mockTraces.find((t) => t.trace_id === "trace-20260926-005-tg-warning");
    expect(tgWarningTrace).toBeDefined();
    if (!tgWarningTrace) return;

    render(
      <TraceSummaryCard
        trace={tgWarningTrace}
        onPreviewFile={dummyPreview}
        onDownloadFile={dummyDownload}
      />
    );

    expect(screen.getByText(/DevOps & SRE Infra Alert Channel/i)).toBeInTheDocument();
    expect(screen.getAllByText(/-1001987654321/).length).toBeGreaterThan(0);
    expect(screen.getByText("telegram")).toBeInTheDocument();
  });

  it("活跃任务看板：能够兼容并列渲染极短耗时（2s）、常规耗时与超长告警耗时（365s）的任务卡片", () => {
    render(
      <ActiveTaskBoard
        tasks={mockActiveTasks}
        onCancelTask={vi.fn()}
        onOpenTrigger={vi.fn()}
        onViewTrace={vi.fn()}
      />
    );

    expect(screen.getByText(/task-live-demo-2-just-started/i)).toBeInTheDocument();
    expect(screen.getByText(/task-live-demo-4-long-duration/i)).toBeInTheDocument();
    expect(screen.getByText(/DevOps & SRE Infra Alert Channel/i)).toBeInTheDocument();
  });

  it("日志矩阵：包含系统启动、DEBUG、多行 ERROR 与 CRITICAL 熔断等多等级拟真日志", () => {
    expect(mockPluginLogs.some((l) => l.level === "DEBUG")).toBe(true);
    expect(mockPluginLogs.some((l) => l.level === "WARNING")).toBe(true);
    expect(mockPluginLogs.some((l) => l.level === "ERROR" && l.message.includes("Traceback"))).toBe(true);
    expect(mockPluginLogs.some((l) => l.level === "CRITICAL")).toBe(true);
    // 包含无 trace_id 的系统启动日志
    expect(mockPluginLogs.some((l) => l.id.startsWith("log-sys-") && !l.trace_id)).toBe(true);
  });
});
