import { useCallback, useEffect, useRef, useState } from "react";
import { fetchManagedRecords, type ManagedRecordEntry } from "../../../entities/plugin-data/api/managedRecordsApi";

export function useStoredRecords(initialKind = "history") {
  const [kind, setKind] = useState(initialKind);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [items, setItems] = useState<ManagedRecordEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const sequence = useRef(0);
  const refresh = useCallback(async () => {
    const request = ++sequence.current;
    setLoading(true);
    try {
      const result = await fetchManagedRecords(kind, search, page);
      if (sequence.current === request) { setItems(result.items); setTotal(result.total); setError(""); }
    } catch (cause) { if (sequence.current === request) setError(cause instanceof Error ? cause.message : "记录列表读取失败"); }
    finally { if (sequence.current === request) setLoading(false); }
  }, [kind, search, page]);
  useEffect(() => { const ref = sequence; void refresh(); return () => { ref.current++; }; }, [refresh]);
  return { kind, setKind, search, setSearch, page, setPage, items, total, loading, error, refresh };
}
