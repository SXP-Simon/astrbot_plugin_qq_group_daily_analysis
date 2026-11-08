import { useCallback, useEffect, useRef, useState } from "react";
import { fetchTraceDetail } from "../../../entities/trace/api/traceApi";
import { fetchTraceLogs } from "../../../entities/log/api/logApi";
import type { TraceRecord } from "../../../entities/trace/model/types";
import type { PluginLogItem } from "../../../entities/log/model/types";

interface DetailState {
  traceId: string | null;
  trace: TraceRecord | null;
  logs: PluginLogItem[];
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  logsError: string | null;
}

const EMPTY_STATE: DetailState = {
  traceId: null,
  trace: null,
  logs: [],
  loading: false,
  refreshing: false,
  error: null,
  logsError: null,
};

export function useTraceDetail(traceId: string | null, open: boolean) {
  const [state, setState] = useState<DetailState>(EMPTY_STATE);
  const refreshRef = useRef<() => void>(() => {});
  const refresh = useCallback(() => refreshRef.current(), []);

  useEffect(() => {
    if (!open || !traceId) {
      setState(EMPTY_STATE);
      return;
    }

    let disposed = false;
    let sequence = 0;
    let latestTrace: TraceRecord | null = null;
    let timer: ReturnType<typeof setTimeout> | undefined;
    setState({ ...EMPTY_STATE, traceId, loading: true });

    // 每轮完成后才安排下一轮；刷新、关闭和切换任务都会使旧响应失效。
    const load = async (forceRefresh: boolean, manual = false) => {
      const request = ++sequence;
      clearTimeout(timer);
      if (manual) {
        setState((previous) => ({
          ...previous,
          loading: latestTrace === null,
          refreshing: true,
        }));
      }
      const [detail, logs] = await Promise.allSettled([
        fetchTraceDetail(traceId, forceRefresh),
        fetchTraceLogs(traceId),
      ]);
      if (disposed || request !== sequence) return;

      if (detail.status === "fulfilled") latestTrace = detail.value;
      setState((previous) => ({
        traceId,
        trace: latestTrace,
        logs: logs.status === "fulfilled" ? logs.value : previous.logs,
        loading: false,
        refreshing: false,
        error:
          detail.status === "rejected"
            ? "任务详情暂时无法更新，请稍后刷新。"
            : detail.value === null
              ? "没有找到这条任务记录，可能已被清理。"
              : null,
        logsError: logs.status === "rejected" ? "日志暂时无法加载，请稍后刷新。" : null,
      }));

      if (latestTrace?.status === "running") {
        timer = setTimeout(() => void load(true), 1500);
      }
    };

    refreshRef.current = () => void load(true, true);
    void load(false);
    return () => {
      disposed = true;
      clearTimeout(timer);
      refreshRef.current = () => {};
    };
  }, [traceId, open]);

  // 属性变更到 effect 清理之间也不展示上一个任务的数据。
  const visible =
    open && traceId
      ? state.traceId === traceId
        ? state
        : { ...EMPTY_STATE, loading: true }
      : EMPTY_STATE;
  const trace = visible.trace;
  const hasWarning =
    Boolean(trace?.extra?.has_warnings) ||
    trace?.spans?.some(
      (span) =>
        span.status === "warning" ||
        span.payload?.success === false ||
        Boolean(span.payload?.warning) ||
        (Array.isArray(span.payload?.subtask_errors) && span.payload.subtask_errors.length > 0),
    );
  const effectiveStatus =
    (trace?.status === "succeeded" || trace?.status === "completed") && hasWarning
      ? "warning"
      : trace?.status || "unknown";

  return { ...visible, effectiveStatus, refresh };
}
