import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { readUploadFile } from "../../../shared/lib/fileUpload";
import type { FileDraft } from "./fileDraft";
import {
  fetchManagedContent,
  fetchManagedFiles,
  fetchManagedPartitions,
  mutateManagedFile,
  deleteManagedFiles,
  type ManagedFileContent,
  type ManagedFileMutation,
  type ManagedPartition,
  type ManagedFile,
  type ManagedFileGroup,
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
  const [deleteResult, setDeleteResult] = useState<{
    deleted: string[];
    failed: { name: string; message: string }[];
  } | null>(null);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [listError, setListError] = useState("");
  const [content, setContent] = useState<ManagedFileContent | null>(null);
  const listSequence = useRef(0);
  const detailSequence = useRef(0);
  const overviewSequence = useRef(0);
  const operation = useRef<number | null>(null);
  const uploadSequence = useRef(0);
  const activeUpload = useRef<number | null>(null);
  const [uploading, setUploading] = useState(false);
  const [actionError, setActionError] = useState("");

  const refresh = useCallback(async () => {
    const request = ++overviewSequence.current;
    try {
      const result = await fetchManagedPartitions();
      if (request !== overviewSequence.current) return;
      setPartitions(result);
      setError("");
    } catch (cause) {
      if (request === overviewSequence.current)
        setError(cause instanceof Error ? cause.message : "存储概览读取失败");
    }
  }, []);

  const load = useCallback(async () => {
    const sequence = ++listSequence.current;
    if (!partition || ["typst_fonts", "avatar_storage"].includes(partition.key)) return;
    setLoading(true);
    try {
      const result = await fetchManagedFiles(partition.key, search, page, extensions, directory);
      if (sequence === listSequence.current) {
        setFiles(result.items);
        setGroups(result.groups || []);
        setTotal(result.total);
        setListError("");
      }
    } catch (cause) {
      if (sequence === listSequence.current)
        setListError(cause instanceof Error ? cause.message : "文件列表读取失败");
    } finally {
      if (sequence === listSequence.current) setLoading(false);
    }
  }, [partition, search, page, extensions, directory]);

  useEffect(() => {
    void refresh();
  }, [refresh]);
  useEffect(() => {
    const sequence = listSequence;
    void load();
    return () => {
      sequence.current++;
    };
  }, [load]);
  useEffect(
    () => () => {
      detailSequence.current++;
      overviewSequence.current++;
      uploadSequence.current++;
    },
    [],
  );

  const select = (value: ManagedPartition | null) => {
    detailSequence.current++;
    listSequence.current++;
    uploadSequence.current++;
    activeUpload.current = null;
    operation.current = null;
    setBusy(false);
    setUploading(false);
    setActionError("");
    setEditor(null);
    setPartition(value);
    setDirectory("");
    setGroups([]);
    setSearch("");
    setExtensions("");
    setPage(1);
    setFiles([]);
    setTotal(0);
    setLoading(false);
    setContent(null);
    setSelected([]);
    setDeleteResult(null);
    setListError("");
  };
  const inspect = async (name: string) => {
    if (!partition || operation.current !== null) return;
    const sequence = ++detailSequence.current;
    operation.current = sequence;
    setActionError("");
    setBusy(true);
    try {
      const result = await fetchManagedContent(partition.key, name);
      if (sequence === detailSequence.current) {
        if (result.name !== name) throw new Error("文件读取结果不匹配，请刷新后重试");
        setContent(result);
      }
    } catch (cause) {
      if (sequence === detailSequence.current)
        toast.error(cause instanceof Error ? cause.message : "文件读取失败");
    } finally {
      if (sequence === detailSequence.current) {
        operation.current = null;
        setBusy(false);
      }
    }
  };
  const mutate = async (input: Omit<ManagedFileMutation, "partition">) => {
    if (!partition || operation.current !== null || activeUpload.current !== null) return false;
    const sequence = detailSequence.current;
    operation.current = sequence;
    setActionError("");
    setBusy(true);
    try {
      await mutateManagedFile({ ...input, partition: partition.key });
      if (sequence !== detailSequence.current) return false;
      setContent(null);
      await Promise.all([load(), refresh()]);
      if (sequence !== detailSequence.current) return false;
      toast.success("文件操作完成");
      return true;
    } catch (cause) {
      if (sequence === detailSequence.current) {
        const detail = cause instanceof Error ? cause.message : "文件操作失败";
        setActionError(detail);
        toast.error(detail);
      }
      return false;
    } finally {
      if (sequence === detailSequence.current) {
        operation.current = null;
        setBusy(false);
      }
    }
  };
  const download = async (name: string) => {
    if (!partition || operation.current !== null) return;
    const sequence = detailSequence.current;
    operation.current = sequence;
    setBusy(true);
    try {
      const result = await fetchManagedContent(partition.key, name);
      if (sequence !== detailSequence.current) return;
      if (result.name !== name) throw new Error("文件读取结果不匹配，请刷新后重试");
      const bytes = Uint8Array.from(atob(result.content_base64), (char) => char.charCodeAt(0));
      const url = URL.createObjectURL(new Blob([bytes], { type: result.media_type }));
      const link = document.createElement("a");
      link.href = url;
      link.download = name.split("/").pop() || "download";
      link.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      if (sequence === detailSequence.current)
        toast.error(cause instanceof Error ? cause.message : "文件下载失败");
    } finally {
      if (sequence === detailSequence.current) {
        operation.current = null;
        setBusy(false);
      }
    }
  };
  const deleteSelected = async () => {
    if (!partition || !selected.length || operation.current !== null) return;
    const sequence = detailSequence.current;
    operation.current = sequence;
    setBusy(true);
    try {
      const result = await deleteManagedFiles(
        partition.key,
        selected.map((file) => ({ name: file.name, revision: file.revision })),
      );
      if (sequence !== detailSequence.current) return;
      setDeleteResult(result);
      setSelected((current) => current.filter((file) => !result.deleted.includes(file.name)));
      await Promise.all([load(), refresh()]);
    } catch (cause) {
      if (sequence === detailSequence.current)
        toast.error(cause instanceof Error ? cause.message : "多选删除失败");
    } finally {
      if (sequence === detailSequence.current) {
        operation.current = null;
        setBusy(false);
      }
    }
  };
  const selectFiles = (keys: React.Key[]) => {
    const known = new Map([...selected, ...files].map((file) => [file.name, file]));
    setSelected(
      keys
        .slice(0, 200)
        .flatMap((key) => (known.get(String(key)) ? [known.get(String(key))!] : [])),
    );
  };
  const prepareUpload = async (file: File, replacement = false, targetName?: string) => {
    if (operation.current !== null) return;
    const sequence = detailSequence.current;
    const request = ++uploadSequence.current;
    activeUpload.current = request;
    const draft = editor;
    setUploading(true);
    setActionError("");
    try {
      const encoded = await readUploadFile(file);
      if (sequence !== detailSequence.current || request !== uploadSequence.current) return;
      if (replacement)
        setEditor((current) => (current && current === draft ? { ...current, encoded } : current));
      else {
        if (targetName && partition?.key === "template_resources") {
          const result = await fetchManagedFiles(partition.key, targetName, 1);
          if (sequence !== detailSequence.current || request !== uploadSequence.current) return;
          const existing = result.items.find((item) => item.name === targetName);
          setEditor({ name: targetName, text: "", encoded, revision: existing?.revision });
          return;
        }
        const prefix =
          partition?.key === "custom_templates" && directory && directory !== "."
            ? `${directory}/`
            : "";
        setEditor({ name: prefix + file.name, text: "", encoded });
      }
    } catch (cause) {
      if (sequence === detailSequence.current && request === uploadSequence.current) {
        const detail = cause instanceof Error ? cause.message : "无法读取上传文件";
        setActionError(detail);
        toast.error(detail);
      }
    } finally {
      if (sequence === detailSequence.current && request === uploadSequence.current) {
        activeUpload.current = null;
        setUploading(false);
      }
    }
  };
  const saveEditor = async () => {
    if (!editor || activeUpload.current !== null) return;
    const encoded =
      editor.encoded ??
      btoa(
        Array.from(new TextEncoder().encode(editor.text), (byte) => String.fromCharCode(byte)).join(
          "",
        ),
      );
    if (
      await mutate({
        name: editor.name,
        operation: editor.revision ? "replace" : "create",
        revision: editor.revision,
        content_base64: encoded,
      })
    )
      setEditor((current) => (current === editor ? null : current));
  };
  const totals = partitions.reduce(
    (value, item) => ({
      totalBytes: value.totalBytes + item.size_bytes,
      totalFiles: value.totalFiles + item.count,
      assetBytes:
        value.assetBytes +
        (["typst_fonts", "template_resources"].includes(item.key) ? item.size_bytes : 0),
    }),
    { totalBytes: 0, totalFiles: 0, assetBytes: 0 },
  );
  return {
    partitions,
    partition,
    files,
    groups,
    directory,
    total,
    totals,
    search,
    extensions,
    page,
    loading,
    busy,
    error,
    listError,
    actionError,
    uploading,
    clearActionError: () => setActionError(""),
    content,
    selected,
    deleteResult,
    editor,
    setEditor,
    cancelEditor: () => {
      uploadSequence.current++;
      activeUpload.current = null;
      setUploading(false);
      setActionError("");
      setEditor(null);
    },
    prepareUpload,
    saveEditor,
    refresh,
    load,
    select,
    inspect,
    download,
    mutate,
    setContent,
    setPage,
    selectDirectory: (value: string) => {
      detailSequence.current++;
      listSequence.current++;
      uploadSequence.current++;
      activeUpload.current = null;
      operation.current = null;
      setBusy(false);
      setUploading(false);
      setActionError("");
      setEditor(null);
      setDirectory(value);
      setSearch("");
      setExtensions("");
      setPage(1);
      setFiles([]);
      setTotal(0);
      setLoading(true);
      setListError("");
      setContent(null);
      setSelected([]);
      setDeleteResult(null);
    },
    deleteSelected,
    selectFiles,
    clearSelection: () => setSelected([]),
    filterExtensions: (value: string) => {
      setExtensions(value);
      setPage(1);
      setSelected([]);
      setDeleteResult(null);
    },
    searchFiles: (value: string) => {
      setSearch(value);
      setPage(1);
      setSelected([]);
      setDeleteResult(null);
    },
  };
}
