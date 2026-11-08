import { useEffect, useRef, useState, useCallback } from "react";
import { z } from "zod";
import { fetchActiveTasks, cancelActiveTask } from "../../../entities/task/api/taskApi";
import { fetchMetricsSummary } from "../../../entities/metric/api/metricApi";
import { acknowledgeTrace, fetchTraceList } from "../../../entities/trace/api/traceApi";
import type { ActiveTask } from "../../../entities/task/model/types";
import type { MetricsSummary } from "../../../entities/metric/model/types";
import type { TraceRecord } from "../../../entities/trace/model/types";

const activeTaskSchema: z.ZodType<ActiveTask> = z.object({
  task_id: z.string().min(1),
  group_id: z.string(),
  group_name: z.string(),
  platform: z.string(),
  trigger_type: z.string(),
  current_stage: z.string(),
  started_at: z.number().finite(),
  duration_s: z.number().finite(),
  last_heartbeat: z.number().finite(),
});
const eventSchema = z.object({ event: z.string(), data: z.unknown() });
const finishedSchema = z.object({ task_id: z.string().min(1) });

export function useOverviewViewModel(active = true) {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [activeTasks, setActiveTasks] = useState<ActiveTask[]>([]);
  const [recentTraces, setRecentTraces] = useState<TraceRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [tasksLoaded, setTasksLoaded] = useState(false);
  const [errors, setErrors] = useState({ tasks: "", metrics: "", recent: "" });
  const [feedback, setFeedback] = useState("");
  const [showAcknowledged, setShowAcknowledged] = useState(false);
  const [acknowledgingIds, setAcknowledgingIds] = useState<string[]>([]);
  const [acknowledgementError, setAcknowledgementError] = useState("");
  const acknowledging = useRef(new Set<string>());
  const requestId = useRef<symbol | null>(null);
  const taskRevision = useRef(0);
  const endedTasks = useRef(new Set<string>());
  const cancelling = useRef(new Set<string>());
  const mounted = useRef(false);
  const activeRef = useRef(active);
  activeRef.current = active;

  const loadData = useCallback(async (silent = false) => {
    if (!mounted.current || !activeRef.current) return;
    const request = Symbol();
    requestId.current = request;
    const revision = taskRevision.current;
    if (!silent) setLoading(true);
    const [tasks, summary, recent] = await Promise.allSettled([
      fetchActiveTasks(),
      fetchMetricsSummary(),
      fetchTraceList({ limit: 20, offset: 0, sort_by: "started_at", sort_order: "desc" }),
    ]);
    if (!mounted.current || request !== requestId.current) return;
    // SSE 比查询快时只放弃活跃列表快照，统计和历史记录仍可独立更新。
    const taskSnapshot =
      tasks.status === "fulfilled" ? z.array(activeTaskSchema).safeParse(tasks.value) : null;
    if (revision === taskRevision.current && taskSnapshot?.success) {
      setActiveTasks(taskSnapshot.data.filter((task) => !endedTasks.current.has(task.task_id)));
      setTasksLoaded(true);
    }
    if (summary.status === "fulfilled") setMetrics(summary.value);
    if (recent.status === "fulfilled") setRecentTraces(recent.value.items);
    setErrors((previous) => ({
      tasks:
        revision !== taskRevision.current
          ? previous.tasks
          : taskSnapshot?.success
            ? ""
            : "运行中任务未能更新，请刷新重试。",
      metrics: summary.status === "fulfilled" ? "" : "统计数据未能更新，请刷新重试。",
      recent: recent.status === "fulfilled" ? "" : "近期分析记录未能更新，请刷新重试。",
    }));
    setLoading(false);
  }, []);

  const handleSSEEvent = useCallback(
    (eventPayload: unknown) => {
      if (!mounted.current) return;
      const parsed = eventSchema.safeParse(eventPayload);
      if (!parsed.success) return;
      const { event, data } = parsed.data;
      if (event === "initial_state") {
        const tasks = z.array(activeTaskSchema).safeParse(data);
        if (!tasks.success) return;
        ++taskRevision.current;
        setActiveTasks(tasks.data.filter((task) => !endedTasks.current.has(task.task_id)));
        setTasksLoaded(true);
        setErrors((previous) => ({ ...previous, tasks: "" }));
      } else if (event === "task_started" || event === "task_progress") {
        const task = activeTaskSchema.safeParse(data);
        if (!task.success || endedTasks.current.has(task.data.task_id)) return;
        ++taskRevision.current;
        setActiveTasks((previous) => {
          const exists = previous.some((item) => item.task_id === task.data.task_id);
          return exists
            ? previous.map((item) => (item.task_id === task.data.task_id ? task.data : item))
            : [task.data, ...previous];
        });
      } else if (["task_finished", "task_canceled", "task_timed_out"].includes(event)) {
        const finished = finishedSchema.safeParse(data);
        if (!finished.success) return;
        ++taskRevision.current;
        endedTasks.current.add(finished.data.task_id);
        if (endedTasks.current.size > 500)
          endedTasks.current.delete(endedTasks.current.values().next().value!);
        setActiveTasks((previous) =>
          previous.filter((task) => task.task_id !== finished.data.task_id),
        );
        void loadData(true);
      }
    },
    [loadData],
  );

  const handleCancelTask = async (taskId: string): Promise<boolean> => {
    if (cancelling.current.has(taskId)) return false;
    cancelling.current.add(taskId);
    try {
      const accepted = await cancelActiveTask(taskId);
      if (accepted && mounted.current) {
        ++taskRevision.current;
        endedTasks.current.add(taskId);
        if (endedTasks.current.size > 500)
          endedTasks.current.delete(endedTasks.current.values().next().value!);
        setActiveTasks((previous) => previous.filter((task) => task.task_id !== taskId));
        setFeedback("中止请求已接受，后台正在清理资源。");
        void loadData(true);
      }
      return accepted;
    } catch {
      return false;
    } finally {
      cancelling.current.delete(taskId);
    }
  };

  const handleAcknowledge = async (traceId: string, acknowledged: boolean) => {
    if (acknowledging.current.has(traceId)) return;
    acknowledging.current.add(traceId);
    setAcknowledgingIds([...acknowledging.current]);
    setAcknowledgementError("");
    try {
      const result = await acknowledgeTrace(traceId, acknowledged);
      if (!mounted.current) return;
      setRecentTraces((previous) =>
        previous.map((trace) =>
          trace.trace_id === traceId
            ? { ...trace, acknowledged_at: result.acknowledged_at }
            : trace,
        ),
      );
      // 新查询取代保存前的旧快照，迟到响应不能撤销刚保存的标记。
      void loadData(true);
    } catch {
      if (mounted.current) setAcknowledgementError("知晓状态未能保存，请稍后重试。");
    } finally {
      acknowledging.current.delete(traceId);
      if (mounted.current) setAcknowledgingIds([...acknowledging.current]);
    }
  };

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      requestId.current = null;
    };
  }, []);
  useEffect(() => {
    if (active) void loadData(false);
    else setLoading(false);
    return () => {
      requestId.current = null;
    };
  }, [active, loadData]);
  const hasActiveTasks = activeTasks.length > 0;
  useEffect(() => {
    if (!active || !hasActiveTasks) return;
    const timer = setInterval(() => {
      const now = Date.now() / 1000;
      setActiveTasks((previous) =>
        previous.map((task) =>
          task.started_at > 0 && task.started_at <= now
            ? {
                ...task,
                duration_s: Math.round((now - task.started_at) * 10) / 10,
              }
            : task,
        ),
      );
    }, 1000);
    return () => clearInterval(timer);
  }, [active, hasActiveTasks]);

  const attentionTraces = recentTraces.filter(
    (trace) =>
      trace.status === "failed" ||
      trace.status === "warning" ||
      (["succeeded", "completed"].includes(trace.status) && trace.extra?.has_warnings === true),
  );
  const acknowledgedCount = attentionTraces.filter(
    (trace) => (trace.acknowledged_at ?? 0) > 0,
  ).length;

  return {
    metrics,
    activeTasks,
    recentTraces,
    attentionTraces: attentionTraces.filter(
      (trace) => showAcknowledged || !(trace.acknowledged_at && trace.acknowledged_at > 0),
    ),
    acknowledgedCount,
    showAcknowledged,
    setShowAcknowledged,
    acknowledgingIds,
    acknowledgementError,
    handleAcknowledge,
    loading,
    tasksLoaded,
    errors,
    feedback,
    refresh: (silent = true) => loadData(silent),
    handleSSEEvent,
    handleCancelTask,
  };
}
