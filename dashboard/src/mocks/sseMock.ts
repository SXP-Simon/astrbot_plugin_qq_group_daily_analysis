/**
 * Mock SSE (Server-Sent Events) 发生器
 * 用于在独立前端开发环境下模拟实时任务流转、阶段变更与日志推送
 */

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
      const progress = (this.tickCount * 15) % 100;
      
      const payload = {
        type: "TASK_UPDATE",
        event: "task_progress",
        data: {
          task_id: "task-live-demo-1",
          trace_id: "trace-20260926-active-01",
          group_id: "123456789",
          stage: progress > 80 ? "report_rendering" : progress > 40 ? "llm_analysis" : "data_fetching",
          progress,
          elapsed_seconds: 40 + this.tickCount * 2,
        },
      };

      this.listeners.forEach((listener) => {
        try {
          listener.onMessage(payload);
        } catch {
          // ignore
        }
      });
    }, 3000);
  }

  public emitManualEvent(event: unknown) {
    this.listeners.forEach((listener) => {
      try {
        listener.onMessage(event);
      } catch {
        // ignore
      }
    });
  }
}

export const mockSSEService = new MockSSEService();
