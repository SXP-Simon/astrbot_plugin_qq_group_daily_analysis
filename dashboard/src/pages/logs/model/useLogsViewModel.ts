import { useCallback, useEffect, useRef, useState } from "react";
import { subscribeSSE } from "@/shared/api/bridge";
import { fetchPluginLogs, clearPluginLogs as apiClearLogs } from "@/entities/log/api/logApi";
import { logEntrySchema, type AvailableTag, type PluginLogItem } from "@/entities/log/model/types";
import { copyToClipboard } from "@/shared/lib/clipboard";

export function useLogsViewModel(active = true) {
  const [logs, setLogs] = useState<PluginLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [availableTags, setAvailableTags] = useState<AvailableTag[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [feedback, setFeedback] = useState("");
  const [clearing, setClearing] = useState(false);
  const [search, setSearch] = useState("");
  const [level, setLevel] = useState<string>();
  const [tag, setTag] = useState<string>();
  const [traceId, setTraceId] = useState<string>();
  const [autoRefresh, setAutoRefresh] = useState(true);
  const requestSequence = useRef(0);
  const pending = useRef<number | null>(null);
  const clearingRef = useRef(false);
  const activeRef = useRef(active);
  const autoRef = useRef(autoRefresh);
  const mounted = useRef(true);
  const knownIds = useRef(new Set<string>());
  const streamed = useRef(new Map<string, PluginLogItem>());
  activeRef.current = active;
  autoRef.current = autoRefresh;

  useEffect(() => {
    const requests = requestSequence;
    mounted.current = true;
    return () => {
      mounted.current = false;
      ++requests.current;
    };
  }, []);

  const loadLogs = useCallback(
    async (silent = false) => {
      if (
        !activeRef.current ||
        clearingRef.current ||
        (silent && (!autoRef.current || pending.current !== null))
      )
        return;
      const request = ++requestSequence.current;
      pending.current = request;
      streamed.current.clear();
      setLoading(!silent);
      setError("");
      try {
        const res = await fetchPluginLogs({
          limit: 200,
          search: search.trim() || undefined,
          level,
          tag,
          trace_id: traceId,
        });
        if (!mounted.current || !activeRef.current || request !== requestSequence.current) return;
        // 请求期间到达的实时日志不能被稍旧的查询快照覆盖。
        const ids = new Set(res.items.map((item) => item.id));
        const additions = [...streamed.current.values()].filter((item) => !ids.has(item.id));
        const items = [...additions, ...res.items]
          .sort((a, b) => b.timestamp - a.timestamp)
          .slice(0, 300);
        knownIds.current = new Set(items.map((item) => item.id));
        setLogs(items);
        setTotal(res.total + additions.length);
        setAvailableTags(res.available_tags);
      } catch (reason) {
        if (mounted.current && activeRef.current && request === requestSequence.current)
          setError(
            reason instanceof Error ? "日志加载失败：" + reason.message : "日志加载失败，请重试。",
          );
      } finally {
        if (pending.current === request) pending.current = null;
        if (mounted.current && request === requestSequence.current) setLoading(false);
      }
    },
    [search, level, tag, traceId],
  );

  useEffect(() => {
    const requests = requestSequence;
    if (active) void loadLogs();
    else setLoading(false);
    return () => {
      ++requests.current;
      pending.current = null;
    };
  }, [active, loadLogs]);

  useEffect(() => {
    if (!active || !autoRefresh) return;
    let listening = true;
    const unsubscribe = subscribeSSE({
      onMessage: (event: unknown) => {
        if (
          !listening ||
          clearingRef.current ||
          !event ||
          typeof event !== "object" ||
          !("event" in event) ||
          event.event !== "log_entry" ||
          !("data" in event)
        )
          return;
        const parsed = logEntrySchema.safeParse(event.data);
        if (!parsed.success) return;
        const entry = parsed.data;
        if (
          (level && entry.level !== level) ||
          (tag && entry.tag.toLowerCase() !== tag.toLowerCase()) ||
          (traceId && entry.trace_id !== traceId)
        )
          return;
        const keyword = search.trim().toLowerCase();
        if (
          keyword &&
          ![
            entry.message,
            entry.trace_id,
            entry.logger_name,
            entry.location,
            entry.function_name,
          ].some((value) => value?.toLowerCase().includes(keyword))
        )
          return;
        if (pending.current !== null) {
          streamed.current.set(entry.id, entry);
          if (streamed.current.size > 300)
            streamed.current.delete(streamed.current.keys().next().value!);
        }
        if (knownIds.current.has(entry.id)) return;
        knownIds.current.add(entry.id);
        if (knownIds.current.size > 600)
          knownIds.current = new Set([...knownIds.current].slice(-300));
        setLogs((previous) =>
          [entry, ...previous].sort((a, b) => b.timestamp - a.timestamp).slice(0, 300),
        );
        setTotal((count) => count + 1);
      },
    });
    return () => {
      listening = false;
      unsubscribe?.();
    };
  }, [active, autoRefresh, level, tag, traceId, search]);

  useEffect(() => {
    if (!active || !autoRefresh) return;
    const requests = requestSequence;
    const timer = setInterval(() => void loadLogs(true), 5000);
    return () => {
      clearInterval(timer);
      ++requests.current;
      pending.current = null;
      setLoading(false);
    };
  }, [active, autoRefresh, loadLogs]);

  const clearLogs = async () => {
    if (clearingRef.current) return false;
    clearingRef.current = true;
    ++requestSequence.current;
    pending.current = null;
    setLoading(false);
    setClearing(true);
    setError("");
    setFeedback("");
    try {
      await apiClearLogs();
      if (!mounted.current) return false;
      knownIds.current.clear();
      streamed.current.clear();
      setLogs([]);
      setTotal(0);
      setFeedback("日志缓冲已清空");
      return true;
    } catch (reason) {
      if (mounted.current)
        setError(
          reason instanceof Error ? "清空日志失败：" + reason.message : "清空日志失败，请重试。",
        );
      return false;
    } finally {
      clearingRef.current = false;
      if (mounted.current) setClearing(false);
    }
  };

  const copyLogs = async () => {
    if (!logs.length) {
      setFeedback("暂无可复制的日志");
      return;
    }
    const ok = await copyToClipboard(logs.map((item) => item.raw).join("\n"));
    if (mounted.current)
      setFeedback(ok ? "已复制 " + logs.length + " 条日志" : "复制失败，请手动选中文本后复制。");
  };

  return {
    logs,
    total,
    availableTags,
    loading,
    error,
    feedback,
    clearing,
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
    clearLogs,
    copyLogs,
    refresh: loadLogs,
  };
}
