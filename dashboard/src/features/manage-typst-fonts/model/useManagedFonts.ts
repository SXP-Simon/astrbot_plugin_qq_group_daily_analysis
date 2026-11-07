import { useCallback, useEffect, useRef, useState } from "react";
import { fetchTypstFonts } from "../../../entities/config/api/configApi";
import type { TypstFontStatus } from "../../../entities/config/model/typstFonts";
import {
  deleteManagedFiles,
  fetchManagedFiles,
  type ManagedFile,
} from "../../../entities/plugin-data/api/managedFilesApi";

import { useFontDownload } from "./useFontDownload";
import { useFontUpload } from "./useFontUpload";
import type { FontManagementSelection } from "./FontManagementContext";

export interface ManagedFontRow {
  name: string;
  file: ManagedFile | null;
  themes: string[];
}

export function useManagedFonts(onChanged: () => void, initialSelection?: FontManagementSelection) {
  const [status, setStatus] = useState<TypstFontStatus | null>(null);
  const downloadQueue = useFontDownload(setStatus, initialSelection?.source);
  const [files, setFiles] = useState<ManagedFile[]>([]);
  const [theme, setTheme] = useState(initialSelection?.theme || "HatsuneMiku");
  const [search, setSearch] = useState("");
  const [format, setFormat] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [requestedPage, setPage] = useState(1);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [removed, setRemoved] = useState<{
    deleted: string[];
    failed: { name: string; message: string }[];
  } | null>(null);
  const sequence = useRef(0);
  const mounted = useRef(true);
  const operating = useRef(false);

  const refresh = useCallback(async () => {
    const request = ++sequence.current;
    setLoading(true);
    try {
      const [fonts, first] = await Promise.all([
        fetchTypstFonts(),
        fetchManagedFiles("typst_fonts", "", 1),
      ]);
      const metadata = [...first.items];
      for (let page = 2; metadata.length < first.total; page++) {
        const next = await fetchManagedFiles("typst_fonts", "", page);
        if (!next.items.length) break;
        metadata.push(...next.items);
      }
      if (request === sequence.current) {
        setStatus(fonts);
        setFiles(metadata);
        setSelected([]);
      }
    } catch (cause) {
      if (request === sequence.current)
        setError(cause instanceof Error ? cause.message : "字体状态读取失败");
    } finally {
      if (request === sequence.current) setLoading(false);
    }
  }, []);

  const fontUpload = useFontUpload(() => {
    void refresh();
    onChanged();
  });

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const requestSequence = sequence;
    return () => {
      mounted.current = false;
      requestSequence.current++;
    };
  }, [refresh]);

  const run = async (action: () => Promise<unknown>) => {
    if (operating.current || fontUpload.running) return false;
    operating.current = true;
    setBusy(true);
    setError("");
    setRemoved(null);
    let success = false;
    try {
      await action();
      success = true;
    } catch (cause) {
      if (mounted.current) setError(cause instanceof Error ? cause.message : "字体操作失败");
    } finally {
      operating.current = false;
      if (mounted.current) {
        setBusy(false);
        void refresh();
        onChanged();
      }
    }
    return success;
  };

  const upload = async (file: File, existing?: ManagedFile | null, presetName?: string) => {
    if (!/\.(ttf|otf|ttc)$/i.test(file.name) || !file.size || file.size > 32 * 1024 * 1024) {
      setError("请选择非空的 TTF、OTF 或 TTC 字体文件，最大 32 MiB");
      return false;
    }
    if (presetName && !status?.presets?.some((preset) => preset.name === presetName)) {
      setError("该字体预设已变化，请刷新状态后重新上传");
      return false;
    }
    if (operating.current) return false;
    setError("");
    setRemoved(null);
    const success = await fontUpload.upload(
      file,
      existing?.name || presetName || file.name,
      existing,
    );
    if (success && !existing && !presetName && mounted.current) setTheme("__all__");
    return success;
  };

  const groups = status?.groups || [];
  const byName = new Map(files.map((file) => [file.name, file]));
  const allNames = [
    ...new Set([
      ...groups.flatMap((group) => group.required),
      ...(status?.missing || []),
      ...files.map((file) => file.name),
    ]),
  ];
  const required = groups.find((group) => group.theme === theme)?.required || allNames;
  const rows: ManagedFontRow[] = required.map((name) => ({
    name,
    file: byName.get(name) || null,
    themes: groups.filter((group) => group.required.includes(name)).map((group) => group.theme),
  }));
  const visible = rows.filter(
    (row) =>
      row.name.toLowerCase().includes(search.toLowerCase()) &&
      (!format || row.name.toLowerCase().endsWith(`.${format}`)),
  );
  const page = Math.min(requestedPage, Math.max(1, Math.ceil(visible.length / 15)));
  return {
    status,
    files,
    groups,
    theme,
    search,
    format,
    selected,
    loading,
    busy: busy || fontUpload.running,
    error,
    removed,
    downloadQueue,
    fontUpload,
    rows: visible,
    page,
    pageRows: visible.slice((page - 1) * 15, page * 15),
    setPage,
    installed: rows.filter((row) => row.file).length,
    required: required.length,
    missing: rows.filter((row) => !row.file).length,
    refresh: async () => {
      setError("");
      await refresh();
      onChanged();
    },
    upload,
    download: (cdn: string) =>
      status
        ? run(() => downloadQueue.download(cdn, theme === "__all__" ? undefined : theme))
        : Promise.resolve(false),
    remove: (targets: ManagedFile[]) =>
      run(async () => {
        const result = await deleteManagedFiles(
          "typst_fonts",
          targets.map((file) => ({ name: file.name, revision: file.revision })),
        );
        if (mounted.current) setRemoved(result);
      }),
    setSelected,
    selectTheme: (value: string) => {
      setPage(1);
      setTheme(value);
      setSelected([]);
    },
    searchFonts: (value: string) => {
      setPage(1);
      setSearch(value);
      setSelected([]);
    },
    filterFormat: (value: string) => {
      setPage(1);
      setFormat(value);
      setSelected([]);
    },
  };
}
