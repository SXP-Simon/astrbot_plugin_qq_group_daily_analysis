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

  const loadData = useCallback(async (silent = false) => {
    if (!silent && !hasLoadedOnce.current) {
      setLoading(true);
    }
    try {
      const [tasks, summary] = await Promise.all([
        fetchActiveTasks(),
        fetchMetricsSummary(),
      ]);
      setActiveTasks(tasks);
      if (summary) setMetrics(summary);
      hasLoadedOnce.current = true;
    } catch {
      // 忽略加载异常
    } finally {
      setLoading(false);
    }
  }, []);

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
    handleCancelTask,
  };
}
