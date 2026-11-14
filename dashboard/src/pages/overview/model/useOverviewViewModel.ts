import { useEffect, useRef, useState, useCallback } from "react";
import { z } from "zod";
import { fetchActiveTasks, cancelActiveTask } from "@/entities/task/api/taskApi";
import { fetchMetricsSummary } from "@/entities/metric/api/metricApi";
import { acknowledgeTrace, fetchTraceList } from "@/entities/trace/api/traceApi";
import type { ActiveTask } from "@/entities/task/model/types";
import type { MetricsSummary } from "@/entities/metric/model/types";
import type { TraceRecord } from "@/entities/trace/model/types";

const activeTaskSchema: z.ZodType<ActiveTask> = z.object({
  task_id: z.string().min(1),
  group_id: z.string(),
  group_name: z.string(),
  platform: z.string(),
  trigger_type: z.string(),
  current_stage: z.string(),
  started_at: z.number(),
  duration_s: z.number(),
  last_heartbeat: z.number(),
});
const eventSchema = z.object({ event: z.string(), data: z.unknown() });
const finishedSchema = z.object({ task_id: z.string().min(1) });

export function useOverviewViewModel(active = true) {
  const [metrics, setMetrics] = useState<MetricsSummary | null>(null);
  const [activeTasks, setActiveTasks] = useState<ActiveTask[]>([]);
  const [recentTraces, setRecentTraces] = useState<TraceRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [recentLoading, setRecentLoading] = useState(false);
  const [metricsLoading, setMetricsLoading] = useState(active);
  const [tasksLoaded, setTasksLoaded] = useState(false);
  const [errors, setErrors] = useState({ tasks: "", metrics: "", recent: "" });
  const [feedback, setFeedback] = useState("");
  const [showAcknowledged, setShowAcknowledged] = useState(false);
  const [acknowledgingIds, setAcknowledgingIds] = useState<string[]>([]);
  const [acknowledgementError, setAcknowledgementError] = useState("");
  const acknowledging = useRef(new Set<string>());
  const requestId = useRef<{ acknowledgements: Map<string, number | null> } | null>(null);
  const metricsRequest = useRef<symbol | null>(null);
  const autoRefresh = useRef<{
    timer: ReturnType<typeof setTimeout> | null;
    running: boolean;
    queued: boolean;
  }>({ timer: null, running: false, queued: false });
  const taskRevision = useRef(0);
  const endedTasks = useRef(new Set<string>());
  const cancelling = useRef(new Set<string>());
  const mounted = useRef(false);
  const activeRef = useRef(active);
  activeRef.current = active;

  const refreshMetrics = useCallback(async () => {
    if (!mounted.current || !activeRef.current) return;
    const request = Symbol();
    metricsRequest.current = request;
    setMetricsLoading(true);
    try {
      const summary = await fetchMetricsSummary();
      if (metricsRequest.current !== request) return;
      setMetrics(summary);
      setErrors((previous) => ({ ...previous, metrics: "" }));
    } catch {
      if (metricsRequest.current !== request) return;
      setErrors((previous) => ({ ...previous, metrics: "统计数据未能更新，请刷新重试。" }));
    } finally {
      if (metricsRequest.current === request) {
        metricsRequest.current = null;
        setMetricsLoading(false);
      }
    }
  }, []);

  const loadData = useCallback(
    async (silent = false) => {
      if (!mounted.current || !activeRef.current) return;
      // 手动刷新也覆盖尚未开始的自动刷新，不再额外排队读取。
      const scheduled = autoRefresh.current;
      if (scheduled.timer !== null) clearTimeout(scheduled.timer);
      scheduled.timer = null;
      scheduled.queued = false;
      const request = { acknowledgements: new Map<string, number | null>() };
      requestId.current = request;
      const revision = taskRevision.current;
      if (!silent) {
        setLoading(true);
        setRecentLoading(true);
      }

      await Promise.all([
        refreshMetrics(),
        fetchActiveTasks()
          .then((tasks) => z.array(activeTaskSchema).parse(tasks))
          .then((tasks) => {
            // SSE 已更新任务时，丢弃较旧的查询快照。
            if (requestId.current !== request || revision !== taskRevision.current) return;
            setActiveTasks(tasks.filter((task) => !endedTasks.current.has(task.task_id)));
            setTasksLoaded(true);
            setErrors((previous) => ({ ...previous, tasks: "" }));
          })
          .catch(() => {
            if (requestId.current !== request || revision !== taskRevision.current) return;
            setErrors((previous) => ({ ...previous, tasks: "运行中任务未能更新，请刷新重试。" }));
          })
          .finally(() => {
            if (requestId.current === request) setLoading(false);
          }),
        fetchTraceList({ limit: 20, offset: 0, sort_by: "started_at", sort_order: "desc" })
          .then((recent) => {
            if (requestId.current !== request) return;
            setRecentTraces(
              recent.items.map((trace) => {
                const saved = request.acknowledgements.get(trace.trace_id);
                return saved === undefined ? trace : { ...trace, acknowledged_at: saved };
              }),
            );
            setErrors((previous) => ({ ...previous, recent: "" }));
          })
          .catch(() => {
            if (requestId.current !== request) return;
            setErrors((previous) => ({
              ...previous,
              recent: "近期分析记录未能更新，请刷新重试。",
            }));
          })
          .finally(() => {
            if (requestId.current === request) setRecentLoading(false);
          }),
      ]);
      if (requestId.current === request) requestId.current = null;
    },
    [refreshMetrics],
  );

  const scheduleRefresh = useCallback(() => {
    if (!mounted.current || !activeRef.current) return;
    const scheduled = autoRefresh.current;
    scheduled.queued = true;
    if (scheduled.timer !== null || scheduled.running) return;
    // 固定短窗口合并密集事件；请求期间的新事件只在完成后补一轮。
    const flush = async () => {
      scheduled.timer = null;
      if (scheduled !== autoRefresh.current || !mounted.current || !activeRef.current) return;
      scheduled.running = true;
      try {
        await loadData(true);
      } finally {
        scheduled.running = false;
        if (
          scheduled === autoRefresh.current &&
          scheduled.queued &&
          mounted.current &&
          activeRef.current
        )
          scheduled.timer = setTimeout(() => void flush(), 100);
      }
    };
    scheduled.timer = setTimeout(() => void flush(), 100);
  }, [loadData]);

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
        scheduleRefresh();
      }
    },
    [scheduleRefresh],
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
        scheduleRefresh();
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
      // 仅覆盖当前未完成查询中的知晓字段，其他任务和统计结果仍可正常更新。
      requestId.current?.acknowledgements.set(traceId, result.acknowledged_at);
      setRecentTraces((previous) =>
        previous.map((trace) =>
          trace.trace_id === traceId
            ? { ...trace, acknowledged_at: result.acknowledged_at }
            : trace,
        ),
      );
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
    const scheduled = autoRefresh.current;
    if (active) void loadData(false);
    else {
      setLoading(false);
      setRecentLoading(false);
      setMetricsLoading(false);
    }
    return () => {
      requestId.current = null;
      metricsRequest.current = null;
      if (scheduled.timer !== null) clearTimeout(scheduled.timer);
      scheduled.queued = false;
      // 隐藏再进入后使用新队列，旧请求完成不能阻塞或触发新一轮读取。
      autoRefresh.current = { timer: null, running: false, queued: false };
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
    recentLoading,
    metricsLoading,
    refreshMetrics,
    tasksLoaded,
    errors,
    feedback,
    refresh: (silent = true) => loadData(silent),
    handleSSEEvent,
    handleCancelTask,
  };
}
