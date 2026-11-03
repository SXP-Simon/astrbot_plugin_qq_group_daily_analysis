import { useCallback, useEffect, useRef, useState } from "react";
import { message } from "antd";
import { readUploadFile } from "../../../shared/lib/fileUpload";
import type { FileDraft } from "./fileDraft";
import {
  fetchManagedContent, fetchManagedFiles, fetchManagedPartitions, mutateManagedFile, deleteManagedFiles,
  type ManagedFileContent, type ManagedFileMutation, type ManagedPartition, type ManagedFile, type ManagedFileGroup,
} from "../../../entities/plugin-data/api/managedFilesApi";

export function useManagedFiles() {
  const [partitions, setPartitions] = useState<ManagedPartition[]>([]);
  const [partition, setPartition] = useState<ManagedPartition | null>(null);
  const [editor, setEditor] = useState<FileDraft | null>(null);
  const [files, setFiles] = useState<ManagedFile[]>([]);
  const [groups, setGroups] = useState<ManagedFileGroup[]>([]);
  const [directory, setDirectory] = useState("");
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [extensions, setExtensions] = useState("");
  const [selected, setSelected] = useState<ManagedFile[]>([]);
  const [deleteResult, setDeleteResult] = useState<{ deleted: string[]; failed: { name: string; message: string }[] } | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [listError, setListError] = useState("");
  const [content, setContent] = useState<ManagedFileContent | null>(null);
  const listSequence = useRef(0);
  const detailSequence = useRef(0);

  const refresh = useCallback(async () => {
    try { setPartitions(await fetchManagedPartitions()); setError(""); }
    catch (cause) { setError(cause instanceof Error ? cause.message : "存储概览读取失败"); }
  }, []);

  const load = useCallback(async () => {
    const sequence = ++listSequence.current;
    if (!partition || ["typst_fonts", "avatar_storage"].includes(partition.key)) return;
    setLoading(true);
    try {
      const result = await fetchManagedFiles(partition.key, search, page, extensions, directory);
      if (sequence === listSequence.current) { setFiles(result.items); setGroups(result.groups || []); setTotal(result.total); setListError(""); }
    } catch (cause) {
      if (sequence === listSequence.current) setListError(cause instanceof Error ? cause.message : "文件列表读取失败");
    } finally { if (sequence === listSequence.current) setLoading(false); }
  }, [partition, search, page, extensions, directory]);

  useEffect(() => { void refresh(); }, [refresh]);
  useEffect(() => { const sequence = listSequence; void load(); return () => { sequence.current++; }; }, [load]);
  useEffect(() => () => { detailSequence.current++; }, []);

  const select = (value: ManagedPartition | null) => {
    detailSequence.current++;
    setEditor(null);
    setPartition(value); setDirectory(""); setGroups([]); setSearch(""); setExtensions(""); setPage(1); setFiles([]); setTotal(0); setLoading(false); setContent(null); setSelected([]); setDeleteResult(null); setListError("");
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
  const download = async (name: string) => {
    if (!partition || busy) return;
    setBusy(true);
    try {
      const result = await fetchManagedContent(partition.key, name);
      const bytes = Uint8Array.from(atob(result.content_base64), char => char.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], { type: result.media_type }));
      const link = document.createElement("a");
      link.href = url; link.download = name.split("/").pop() || "download";
      link.click(); URL.revokeObjectURL(url);
    } catch (cause) { void message.error(cause instanceof Error ? cause.message : "文件下载失败"); }
    finally { setBusy(false); }
  };
  const deleteSelected = async () => {
    if (!partition || !selected.length) return;
    setBusy(true);
    try {
      const result = await deleteManagedFiles(partition.key, selected.map(file => ({ name: file.name, revision: file.revision })));
      setDeleteResult(result);
      setSelected(current => current.filter(file => !result.deleted.includes(file.name)));
      await Promise.all([load(), refresh()]);
    } catch (cause) { void message.error(cause instanceof Error ? cause.message : "多选删除失败"); }
    finally { setBusy(false); }
  };
  const selectFiles = (keys: React.Key[]) => {
    const known = new Map([...selected, ...files].map(file => [file.name, file]));
    setSelected(keys.slice(0, 200).flatMap(key => known.get(String(key)) ? [known.get(String(key))!] : []));
  };
  const prepareUpload = async (file: File, replacement = false) => {
    const sequence = detailSequence.current;
    try {
      const encoded = await readUploadFile(file);
      if (sequence !== detailSequence.current) return;
      if (replacement) setEditor(current => current && { ...current, encoded });
      else {
        const prefix = partition?.key === "custom_templates" && directory && directory !== "." ? `${directory}/` : "";
        setEditor({ name: prefix + file.name, text: "", encoded });
      }
    } catch (cause) { if (sequence === detailSequence.current) void message.error(cause instanceof Error ? cause.message : "无法读取上传文件"); }
  };
  const saveEditor = async () => {
    if (!editor) return;
    const encoded = editor.encoded ?? btoa(Array.from(new TextEncoder().encode(editor.text), byte => String.fromCharCode(byte)).join(""));
    if (await mutate({ name: editor.name, operation: editor.revision ? "replace" : "create", revision: editor.revision, content_base64: encoded })) setEditor(null);
  };
  const totals = partitions.reduce((value, item) => ({ totalBytes: value.totalBytes + item.size_bytes, totalFiles: value.totalFiles + item.count,
    assetBytes: value.assetBytes + (["typst_fonts", "template_resources"].includes(item.key) ? item.size_bytes : 0) }), { totalBytes: 0, totalFiles: 0, assetBytes: 0 });
  return { partitions, partition, files, groups, directory, total, totals, search, extensions, page, loading, busy, error, listError, content, selected, deleteResult, editor, setEditor, prepareUpload, saveEditor,
    refresh, load, select, inspect, download, mutate, setContent, setPage,
    selectDirectory: (value: string) => { detailSequence.current++; setEditor(null); setDirectory(value); setSearch(""); setExtensions(""); setPage(1); setFiles([]); setTotal(0); setLoading(true); setListError(""); setContent(null); setSelected([]); setDeleteResult(null); },
    deleteSelected, selectFiles, clearSelection: () => setSelected([]),
    filterExtensions: (value: string) => { setExtensions(value); setPage(1); setSelected([]); setDeleteResult(null); },
    searchFiles: (value: string) => { setSearch(value); setPage(1); setSelected([]); setDeleteResult(null); } };
}
