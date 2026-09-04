import { useEffect, useRef, useState } from "react";
import { message } from "antd";
import { subscribeSSE } from "../../../shared/api/bridge";
import {
  fetchPluginLogs,
  clearPluginLogs as apiClearLogs,
} from "../../../entities/log/api/logApi";
import { AvailableTag, PluginLogItem } from "../../../entities/log/model/types";

export function useLogsViewModel() {
  const [logs, setLogs] = useState<PluginLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [availableTags, setAvailableTags] = useState<AvailableTag[]>([]);
  const [loading, setLoading] = useState(false);

  // 筛选条件
  const [search, setSearch] = useState("");
  const [level, setLevel] = useState<string | undefined>(undefined);
  const [tag, setTag] = useState<string | undefined>(undefined);
  const [traceId, setTraceId] = useState<string | undefined>(undefined);
  const [autoRefresh, setAutoRefresh] = useState(true);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const loadLogs = async (silent = false) => {
    if (!silent) setLoading(true);
    try {
      const res = await fetchPluginLogs({
        limit: 200,
        search: search.trim() || undefined,
        level: level || undefined,
        tag: tag || undefined,
        trace_id: traceId || undefined,
      });
      setLogs(res.items || []);
      setTotal(res.total || 0);
      if (res.available_tags && res.available_tags.length > 0) {
        setAvailableTags(res.available_tags);
      }
    } catch {
      // 忽略加载异常
    } finally {
      if (!silent) setLoading(false);
    }
  };

  const handleClearLogs = async () => {
    try {
      await apiClearLogs();
      setLogs([]);
      setTotal(0);
      message.success("日志缓冲已清空");
    } catch {
      message.error("清空日志失败");
    }
  };

  // 初始与条件变化加载
  useEffect(() => {
    loadLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search, level, tag, traceId]);

  // SSE 实时推流：收到后端 log_entry 毫秒级直接上屏
  useEffect(() => {
    const unsubscribe = subscribeSSE({
      onMessage: (eventPayload: unknown) => {
        if (!autoRefresh) return;
        if (
          eventPayload &&
          typeof eventPayload === "object" &&
          "event" in eventPayload &&
          (eventPayload as { event: string }).event === "log_entry"
        ) {
          const entry = (eventPayload as unknown as { data?: PluginLogItem })?.data;
          if (entry && entry.id) {
            // 实时检查是否匹配当前筛选条件
            if (level && entry.level !== level) return;
            if (tag && entry.tag.toLowerCase() !== tag.toLowerCase()) return;
            if (traceId && entry.trace_id !== traceId) return;
            if (
              search.trim() &&
              !entry.message.toLowerCase().includes(search.trim().toLowerCase()) &&
              !(entry.trace_id || "").toLowerCase().includes(search.trim().toLowerCase()) &&
              !entry.logger_name.toLowerCase().includes(search.trim().toLowerCase())
            ) {
              return;
            }

            setLogs((prev) => {
              // 防重
              if (prev.some((item) => item.id === entry.id)) return prev;
              return [entry, ...prev.slice(0, 300)];
            });
            setTotal((t) => t + 1);
          }
        }
      },
    });

    return () => {
      if (unsubscribe) unsubscribe();
    };
  }, [autoRefresh, level, tag, traceId, search]);

  // 兜底轮询 (每 5 秒同步一次全量指标与未连接状态)
  useEffect(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    if (autoRefresh) {
      pollRef.current = setInterval(() => {
        loadLogs(true);
      }, 5000);
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoRefresh, search, level, tag, traceId]);

  return {
    logs,
    total,
    availableTags,
    loading,
    search,
    setSearch,
    level,
    setLevel,
    tag,
    setTag,
    traceId,
    setTraceId,
    autoRefresh,
    setAutoRefresh,
    clearLogs: handleClearLogs,
    refresh: (silent = false) => loadLogs(silent),
  };
}
