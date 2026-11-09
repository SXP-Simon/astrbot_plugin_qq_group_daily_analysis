import { afterEach, expect, it, vi } from "vitest";
import { mockSSEService } from "@/mocks/sseMock";
import { mockActiveTasks } from "@/mocks/data/tasks";
import { mockPluginLogs } from "@/mocks/data/logs";
import { mockHandlers } from "@/mocks/handlers";
import { logEntrySchema } from "@/entities/log/model/types";

afterEach(() => vi.useRealTimers());

it("手动注入更新已有任务并关联日志，不创造不存在的任务", () => {
  vi.useFakeTimers();
  const initialLogs = [...mockPluginLogs];
  const tasks = mockActiveTasks.map((task) => ({ ...task }));
  const receive = vi.fn();
  const cleanup = mockSSEService.subscribe({ onMessage: receive });
  try {
    const task = mockActiveTasks[0];
    expect(mockSSEService.emitTaskHeartbeat(task.task_id)).toBe(true);
    expect(receive.mock.calls[0][0]).toEqual({ event: "task_progress", data: task });
    expect(receive.mock.calls[1][0].data.trace_id).toBe(task.task_id);
    expect(mockSSEService.emitTaskHeartbeat("not-an-active-task")).toBe(false);
    expect(receive).toHaveBeenCalledTimes(2);
    expect(mockActiveTasks).toHaveLength(tasks.length);
  } finally {
    cleanup();
    mockPluginLogs.splice(0, mockPluginLogs.length, ...initialLogs);
    mockActiveTasks.splice(0, mockActiveTasks.length, ...tasks);
  }
});

it("实时事件、详情和日志查询引用同一个活跃任务，注销后不继续产生事件", () => {
  vi.useFakeTimers();
  const initialLogs = [...mockPluginLogs];
  const tasks = mockActiveTasks.map((task) => ({ ...task }));
  const receive = vi.fn();
  const cleanup = mockSSEService.subscribe({ onMessage: receive });
  try {
    vi.advanceTimersByTime(3000);
    const progress = receive.mock.calls[0][0];
    const log = receive.mock.calls[1][0];
    const task = mockActiveTasks.find((item) => item.task_id === progress.data.task_id);
    expect(task).toBeDefined();
    expect(progress).toEqual({ event: "task_progress", data: task });
    expect(progress.data).not.toHaveProperty("progress");
    expect(log.event).toBe("log_entry");
    expect(logEntrySchema.safeParse(log.data).success).toBe(true);
    expect(log.data.message).toContain("演示");
    expect(log.data.trace_id).toBe(task?.task_id);
    expect(log.data.stage).toBe(task?.current_stage);
    expect(log.data.location).toBe("demo_task_runner.py:68");
    expect(log.data.function_name).toBe("DemoTaskRunner.heartbeat");
    expect(log.data.raw).toContain("[demo_task_runner.py:68] [DemoTaskRunner.heartbeat]");
    expect(
      mockHandlers["GET logs"]({ search: "DemoTaskRunner.heartbeat" }).data.items,
    ).toContainEqual(log.data);
    expect(
      mockHandlers["GET logs"]({ search: "demo_task_runner.py:68" }).data.items,
    ).toContainEqual(log.data);
    expect(mockHandlers["GET logs"]({ trace_id: "not-a-task" }).data.items).toEqual([]);
    expect(
      mockHandlers["GET traces/:traceId"](undefined, { traceId: log.data.trace_id }).data,
    ).toMatchObject({
      trace_id: task?.task_id,
      group_id: task?.group_id,
      platform: task?.platform,
      current_stage: task?.current_stage,
    });
    expect(
      mockHandlers["GET traces/:traceId/logs"](undefined, { traceId: log.data.trace_id }).data,
    ).toContainEqual(log.data);
    expect(mockHandlers["GET logs"]({ trace_id: log.data.trace_id }).data.items).toContainEqual(
      log.data,
    );
    cleanup();
    const count = receive.mock.calls.length;
    vi.advanceTimersByTime(9000);
    expect(receive).toHaveBeenCalledTimes(count);
    expect(vi.getTimerCount()).toBe(0);
  } finally {
    cleanup();
    mockPluginLogs.splice(0, mockPluginLogs.length, ...initialLogs);
    mockActiveTasks.splice(0, mockActiveTasks.length, ...tasks);
  }
});
