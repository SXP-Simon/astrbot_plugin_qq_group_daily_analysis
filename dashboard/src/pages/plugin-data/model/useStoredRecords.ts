import { useCallback, useEffect, useRef, useState } from "react";
import {
  fetchManagedRecords,
  type ManagedRecordEntry,
} from "@/entities/plugin-data/api/managedRecordsApi";

type RecordKind = "history" | "avatar";
export function useStoredRecords(initialKind: RecordKind = "history") {
  const [query, setQuery] = useState({ kind: initialKind, search: "", page: 1 });
  const current = useRef(query);
  const [items, setItems] = useState<ManagedRecordEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const sequence = useRef(0);
  const changeQuery = useCallback((changes: Partial<typeof query>) => {
    const next = { ...current.current, ...changes };
    if (!Number.isSafeInteger(next.page) || next.page < 1) next.page = 1;
    if (JSON.stringify(next) === JSON.stringify(current.current)) return;
    const filtersChanged =
      next.kind !== current.current.kind || next.search !== current.current.search;
    sequence.current++;
    current.current = next;
    setQuery(next);
    setLoading(true);
    setItems([]);
    // 只切页时保留已知总数，允许继续选择目标页。
    if (filtersChanged) setTotal(0);
    setError("");
  }, []);
  const refresh = useCallback(async () => {
    const request = ++sequence.current;
    const { kind, search, page } = current.current;
    setLoading(true);
    setError("");
    try {
      const result = await fetchManagedRecords(kind, search, page);
      if (sequence.current !== request) return;
      const lastPage = Math.max(1, Math.ceil(result.total / 20));
      if (page > lastPage) {
        changeQuery({ page: lastPage });
        return;
      }
      setItems(result.items);
      setTotal(result.total);
    } catch (cause) {
      if (sequence.current === request)
        setError(cause instanceof Error ? cause.message : "记录列表读取失败");
    } finally {
      if (sequence.current === request) setLoading(false);
    }
  }, [changeQuery]);
  useEffect(() => {
    changeQuery({ kind: initialKind, search: "", page: 1 });
  }, [initialKind, changeQuery]);
  useEffect(() => {
    const ref = sequence;
    void refresh();
    return () => {
      ref.current++;
    };
  }, [query, refresh]);
  return {
    ...query,
    setKind: (kind: RecordKind) => changeQuery({ kind, page: 1 }),
    setSearch: (search: string) => changeQuery({ search: search.trim(), page: 1 }),
    setPage: (page: number) => changeQuery({ page }),
    items,
    total,
    loading,
    error,
    refresh,
  };
}
