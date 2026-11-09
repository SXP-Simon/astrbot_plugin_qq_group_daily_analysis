import { describe, it, expect, vi } from "vitest";
import { act, render, screen, fireEvent, within, waitFor } from "@testing-library/react";
import { ActiveTaskBoard } from "@/widgets/active-task-board/ActiveTaskBoard";
import { mockActiveTasks } from "@/mocks/data/tasks";

const tasks = mockActiveTasks.slice(1, 3);
const callbacks = () => ({ onCancelTask: vi.fn(), onOpenTrigger: vi.fn(), onViewTrace: vi.fn() });

describe("运行中任务看板", () => {
  it("同时展示多个群聊与独立入口，基础统计不误报为大模型分析", () => {
    const props = callbacks();
    render(
      <ActiveTaskBoard
        tasks={[
          { ...tasks[0], current_stage: "STATS_ANALYSIS", duration_s: 0 },
          { ...tasks[1], duration_s: Number.NaN },
        ]}
        {...props}
      />,
    );
    expect(screen.getByRole("heading", { name: /2 运行中/ })).toBeVisible();
    expect(screen.getByText("基础统计分析")).toBeVisible();
    expect(screen.getByText("0 秒")).toBeVisible();
    expect(screen.getByText("未记录")).toBeVisible();
    const rows = screen.getAllByRole("listitem");
    expect(within(rows[0]).getByText(tasks[0].group_name)).toBeVisible();
    expect(within(rows[1]).getByText(tasks[1].task_id)).toBeVisible();
    fireEvent.click(within(rows[1]).getByRole("button", { name: "查看详情" }));
    expect(props.onViewTrace).toHaveBeenCalledWith(tasks[1].task_id);
    fireEvent.click(screen.getByRole("button", { name: "发起分析" }));
    expect(props.onOpenTrigger).toHaveBeenCalledOnce();
  });

  it("中止前显示任务身份并聚焦继续分析；确认只提交所选任务且阻止重复点击", async () => {
    let finish!: (accepted: boolean) => void;
    const props = {
      ...callbacks(),
      onCancelTask: vi.fn(
        () =>
          new Promise<boolean>((resolve) => {
            finish = resolve;
          }),
      ),
    };
    render(<ActiveTaskBoard tasks={tasks} {...props} />);
    const trigger = screen.getAllByRole("button", { name: "中止" })[1];
    fireEvent.click(trigger);
    const dialog = screen.getByRole("dialog");
    expect(within(dialog).getByText(tasks[1].task_id)).toBeVisible();
    expect(within(dialog).getByRole("button", { name: "继续分析" })).toHaveFocus();
    expect(props.onCancelTask).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: "确认中止" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "正在请求…" }));
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.getByRole("dialog")).toBeVisible();
    expect(props.onCancelTask).toHaveBeenCalledOnce();
    expect(props.onCancelTask).toHaveBeenCalledWith(tasks[1].task_id);
    await act(async () => finish(true));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("拒绝或异常保留确认弹窗并允许重试；关闭恢复原按钮焦点", async () => {
    const props = {
      ...callbacks(),
      onCancelTask: vi.fn().mockResolvedValueOnce(false).mockRejectedValueOnce(new Error("离线")),
    };
    render(<ActiveTaskBoard tasks={tasks} {...props} />);
    const trigger = screen.getAllByRole("button", { name: "中止" })[0];
    fireEvent.click(trigger);
    fireEvent.click(screen.getByRole("button", { name: "确认中止" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("中止请求未成功");
    fireEvent.click(screen.getByRole("button", { name: "确认中止" }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("检查连接后重试"));
    expect(props.onCancelTask).toHaveBeenCalledTimes(2);
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    await waitFor(() => expect(trigger).toHaveFocus());
  });

  it("确认期间任务消失后焦点回到看板，迟到回执不重新打开弹窗", async () => {
    let finish!: () => void;
    const props = {
      ...callbacks(),
      onCancelTask: vi.fn(
        () =>
          new Promise<void>((resolve) => {
            finish = resolve;
          }),
      ),
    };
    const { rerender } = render(<ActiveTaskBoard tasks={tasks} {...props} />);
    fireEvent.click(screen.getAllByRole("button", { name: "中止" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "确认中止" }));
    rerender(<ActiveTaskBoard tasks={tasks.slice(1)} {...props} />);
    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /正在执行中的分析任务/ })).toHaveFocus(),
    );
    await act(async () => finish());
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("空列表保留发起入口", () => {
    const props = callbacks();
    render(<ActiveTaskBoard tasks={[]} {...props} />);
    expect(screen.getByText("暂无正在执行的后台分析任务")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: "发起分析" }));
    expect(props.onOpenTrigger).toHaveBeenCalledOnce();
  });
});
