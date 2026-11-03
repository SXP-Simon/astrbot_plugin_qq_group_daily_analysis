import { useCallback, useEffect, useRef, useState } from "react";
import { message } from "antd";
import {
  fetchManagedContent, fetchManagedFiles, fetchManagedPartitions, mutateManagedFile,
  type ManagedFileContent, type ManagedFileMutation, type ManagedPartition, type ManagedFile,
} from "../../../entities/plugin-data/api/managedFilesApi";

export function useManagedFiles() {
  const [partitions, setPartitions] = useState<ManagedPartition[]>([]);
  const [partition, setPartition] = useState<ManagedPartition | null>(null);
  const [files, setFiles] = useState<ManagedFile[]>([]);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [content, setContent] = useState<ManagedFileContent | null>(null);
  const listSequence = useRef(0);
  const detailSequence = useRef(0);

  const refresh = useCallback(async () => {
    try { setPartitions(await fetchManagedPartitions()); setError(""); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "存储概览读取失败"); }
  }, []);

  const load = useCallback(async () => {
    const sequence = ++listSequence.current;
    if (!partition) return;
    setLoading(true);
    try {
      const result = await fetchManagedFiles(partition.key, search, page);
      if (sequence === listSequence.current) { setFiles(result.items); setTotal(result.total); setError(""); }
    } catch (cause) {
      if (sequence === listSequence.current) setError(cause instanceof Error ? cause.message : "文件列表读取失败");
    } finally { if (sequence === listSequence.current) setLoading(false); }
  }, [partition, search, page]);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => { const sequence = listSequence; void load(); return () => { sequence.current++; }; }, [load]);
  useEffect(() => () => { detailSequence.current++; }, []);

  const select = (value: ManagedPartition | null) => {
    detailSequence.current++;
    setPartition(value); setSearch(""); setPage(1); setFiles([]); setContent(null);
  };
  const inspect = async (name: string) => {
    if (!partition || busy) return;
    const sequence = ++detailSequence.current;
    setBusy(true);
    try {
      const result = await fetchManagedContent(partition.key, name);
      if (sequence === detailSequence.current) setContent(result);
    } catch (cause) { void message.error(cause instanceof Error ? cause.message : "文件读取失败"); }
    finally { setBusy(false); }
  };
  const mutate = async (input: Omit<ManagedFileMutation, "partition">) => {
    if (!partition) return false;
    setBusy(true);
    try {
      await mutateManagedFile({ ...input, partition: partition.key });
      setContent(null);
      await Promise.all([load(), refresh()]);
      void message.success("文件操作完成");
      return true;
    } catch (cause) { void message.error(cause instanceof Error ? cause.message : "文件操作失败"); return false; }
    finally { setBusy(false); }
  };
  return { partitions, partition, files, total, search, page, loading, busy, error, content,
    refresh, load, select, inspect, mutate, setContent, setPage,
    searchFiles: (value: string) => { setSearch(value); setPage(1); } };
}
