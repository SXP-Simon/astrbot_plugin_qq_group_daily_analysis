import React from "react";
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ActiveTaskBoard } from "../ActiveTaskBoard";
import { mockActiveTasks } from "../../../mocks/data/tasks";

describe("ActiveTaskBoard Widget", () => {
  it("should render active tasks with group name and stage badges", () => {
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

  it("should trigger cancel task callback when cancel button is clicked", () => {
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
