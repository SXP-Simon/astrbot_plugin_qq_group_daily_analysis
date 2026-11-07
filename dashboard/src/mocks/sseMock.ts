/**
 * Mock SSE (Server-Sent Events) 发生器
 * 用于在独立前端开发环境下模拟实时任务流转、阶段变更与日志推送
 */

import { mockActiveTasks } from "./data/tasks";
import { mockPluginLogs } from "./data/logs";
import type { PluginLogItem } from "../entities/log/model/types";

export interface SSEListener {
  onMessage: (event: unknown) => void;
  onError?: () => void;
}

class MockSSEService {
  private listeners = new Set<SSEListener>();
  private timer: number | null = null;
  private tickCount = 0;

  public subscribe(listener: SSEListener): () => void {
    this.listeners.add(listener);
    if (!this.timer && typeof window !== "undefined") {
      this.startEmitting();
    }
    return () => {
      this.listeners.delete(listener);
      if (this.listeners.size === 0 && this.timer) {
        clearInterval(this.timer);
        this.timer = null;
      }
    };
  }

  private startEmitting() {
    this.timer = window.setInterval(() => {
      this.tickCount++;
      const task = mockActiveTasks[(this.tickCount - 1) % mockActiveTasks.length];
      if (!task) return;
      const date = new Date();
      task.last_heartbeat = date.getTime() / 1000;
      task.duration_s = Math.max(0, task.last_heartbeat - task.started_at);
      // 只更新真实示例任务的心跳，不循环伪造完成比例或退回前一阶段。
      this.emitManualEvent({ event: "task_progress", data: { ...task } });
      const time =
        date.toLocaleString("sv-SE") + "." + String(date.getMilliseconds()).padStart(3, "0");
      const message = "演示：任务仍在运行，当前阶段 " + task.current_stage;
      const entry: PluginLogItem = {
        id: "mock-live-log-" + this.tickCount,
        timestamp: task.last_heartbeat,
        time_str: time,
        level: "DEBUG",
        logger_name: "astrbot_plugin_qq_group_daily_analysis.mock",
        location: "demo_task_runner.py:68",
        function_name: "DemoTaskRunner.heartbeat",
        tag: "Trace",
        trace_id: task.task_id,
        stage: task.current_stage,
        message,
        raw:
          "[" + time + "] [DEBUG] [demo_task_runner.py:68] [DemoTaskRunner.heartbeat]: " + message,
      };
      mockPluginLogs.unshift(entry);
      if (mockPluginLogs.length > 2000) mockPluginLogs.length = 2000;
      this.emitManualEvent({ event: "log_entry", data: entry });
    }, 3000);
  }

  public emitManualEvent(event: unknown) {
    this.listeners.forEach((listener) => {
      try {
        listener.onMessage(event);
      } catch {
        // 单个演示订阅失败不影响其他页面。
      }
    });
  }
}

export const mockSSEService = new MockSSEService();
