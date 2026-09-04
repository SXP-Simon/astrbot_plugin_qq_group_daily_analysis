import { useEffect, useRef, useState, useCallback } from "react";
import { fetchActiveTasks, cancelActiveTask } from "../../../entities/task/api/taskApi";
import { fetchMetricsSummary } from "../../../entities/metric/api/metricApi";
import { ActiveTask } from "../../../entities/task/model/types";
import { MetricsSummary } from "../../../entities/metric/model/types";

export function useOverviewViewModel() {
  const [metrics, setMetrics] = useState<MetricsSummary>({
    total_traces: 0,
    succeeded_count: 0,
    failed_count: 0,
    success_rate: 0,
    avg_duration_ms: 0,
    today_traces: 0,
    today_active_groups: 0,
    total_tokens_spent: 0,
    total_cost_spent: 0,
    today_tokens_spent: 0,
    today_cost_spent: 0,
  });
  const [activeTasks, setActiveTasks] = useState<ActiveTask[]>([]);
  const [loading, setLoading] = useState(false);
  const hasLoadedOnce = useRef(false);
  const reqIdRef = useRef(0);

  const loadData = useCallback(async (silent = false) => {
    const currentReqId = ++reqIdRef.current;
    if (!silent && !hasLoadedOnce.current) {
      setLoading(true);
    }
    try {
      const [tasks, summary] = await Promise.all([
        fetchActiveTasks(),
        fetchMetricsSummary(),
      ]);
      // 忽略陈旧的过时异步响应，防止覆盖最新的 SSE 状态
      if (currentReqId !== reqIdRef.current) return;
      setActiveTasks(tasks);
      if (summary) setMetrics(summary);
      hasLoadedOnce.current = true;
    } catch {
      // 忽略加载异常
    } finally {
      if (currentReqId === reqIdRef.current) {
        setLoading(false);
      }
    }
  }, []);

  const handleSSEEvent = useCallback(
    (eventPayload: unknown) => {
      if (!eventPayload || typeof eventPayload !== "object") return;
      const evt = eventPayload as { event?: string; data?: unknown };
      if (!evt.event) return;

      if (evt.event === "initial_state") {
        if (Array.isArray(evt.data)) {
          setActiveTasks(evt.data as ActiveTask[]);
        }
      } else if (evt.event === "task_started") {
        const newTask = evt.data as ActiveTask;
        if (newTask && newTask.task_id) {
          setActiveTasks((prev) => {
            const filtered = prev.filter((t) => t.task_id !== newTask.task_id);
            return [newTask, ...filtered];
          });
        }
      } else if (evt.event === "task_progress") {
        const updatedTask = evt.data as ActiveTask;
        if (updatedTask && updatedTask.task_id) {
          setActiveTasks((prev) =>
            prev.map((t) =>
              t.task_id === updatedTask.task_id
                ? { ...t, ...updatedTask }
                : t
            )
          );
        }
      } else if (evt.event === "task_finished") {
        const finishData = evt.data as { task_id?: string } | undefined;
        if (finishData?.task_id) {
          setActiveTasks((prev) =>
            prev.filter((t) => t.task_id !== finishData.task_id)
          );
        }
        // 任务完成时使先前可能在途中的全量拉取失效，并静默刷新总览 KPI 指标
        loadData(true);
      }
    },
    [loadData]
  );

  const handleCancelTask = async (taskId: string) => {
    await cancelActiveTask(taskId);
    await loadData(true);
  };

  useEffect(() => {
    loadData(false);
    // 活跃任务动态计时器 (每秒刷新运行时长)
    const timer = setInterval(() => {
      setActiveTasks((prev) =>
        prev.map((t) => ({
          ...t,
          duration_s: Math.round((Date.now() / 1000 - t.started_at) * 10) / 10,
        }))
      );
    }, 1000);

    return () => clearInterval(timer);
  }, [loadData]);

  return {
    metrics,
    activeTasks,
    loading,
    refresh: (silent = true) => loadData(silent),
    handleSSEEvent,
    handleCancelTask,
  };
}
