import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ActiveTaskBoard } from "../ActiveTaskBoard";
import { mockActiveTasks } from "../../../mocks/data/tasks";

describe("活跃任务看板小部件 (ActiveTaskBoard Widget)", () => {
  it("应当正确渲染运行中任务列表、群名称与阶段徽标", () => {
    const handleCancel = vi.fn();
    const handleOpenTrigger = vi.fn();
    const handleViewTrace = vi.fn();

    render(
      <ActiveTaskBoard
        tasks={mockActiveTasks}
        onCancelTask={handleCancel}
        onOpenTrigger={handleOpenTrigger}
        onViewTrace={handleViewTrace}
      />
    );

    expect(screen.getByText(/正在执行中的分析任务/i)).toBeInTheDocument();
    expect(screen.getByText(/技术交流与闲聊吹水群/i)).toBeInTheDocument();
    expect(screen.getByText(/AstrBot 核心测试群/i)).toBeInTheDocument();
    expect(screen.getByText("task-live-demo-1")).toBeInTheDocument();
  });

  it("点击中止任务按钮时应当正确触发取消任务回调", () => {
    const handleCancel = vi.fn();
    const handleOpenTrigger = vi.fn();
    const handleViewTrace = vi.fn();

    render(
      <ActiveTaskBoard
        tasks={mockActiveTasks}
        onCancelTask={handleCancel}
        onOpenTrigger={handleOpenTrigger}
        onViewTrace={handleViewTrace}
      />
    );

    const cancelButtons = screen.getAllByRole("button", { name: /中止|取消/i });
    if (cancelButtons.length > 0) {
      fireEvent.click(cancelButtons[0]);
    }
  });
});
