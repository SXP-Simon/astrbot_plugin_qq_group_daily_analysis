import { useCallback, useEffect, useRef, useState } from "react";
import { readUploadFile } from "../../../shared/lib/fileUpload";
import { fetchTypstFonts } from "../../../entities/config/api/configApi";
import type { TypstFontStatus } from "../../../entities/config/model/typstFonts";
import { deleteManagedFiles, fetchManagedFiles, mutateManagedFile, type ManagedFile } from "../../../entities/plugin-data/api/managedFilesApi";

import { useFontDownload } from "./useFontDownload";

export interface ManagedFontRow { name: string; file: ManagedFile | null; themes: string[] }

export function useManagedFonts(onChanged: () => void) {
  const [status, setStatus] = useState<TypstFontStatus | null>(null);
  const downloadQueue = useFontDownload(setStatus);
  const [files, setFiles] = useState<ManagedFile[]>([]);
  const [theme, setTheme] = useState("HatsuneMiku");
  const [search, setSearch] = useState("");
  const [format, setFormat] = useState("");
  const [selected, setSelected] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [removed, setRemoved] = useState<{ deleted: string[]; failed: { name: string; message: string }[] } | null>(null);
  const sequence = useRef(0);
  const mounted = useRef(true);
  const operating = useRef(false);

  const refresh = useCallback(async () => {
    const request = ++sequence.current;
    setLoading(true);
    try {
      const [fonts, first] = await Promise.all([fetchTypstFonts(), fetchManagedFiles("typst_fonts", "", 1)]);
      const metadata = [...first.items];
      for (let page = 2; metadata.length < first.total; page++) {
        const next = await fetchManagedFiles("typst_fonts", "", page);
        if (!next.items.length) break;
        metadata.push(...next.items);
      }
      if (request === sequence.current) { setStatus(fonts); setFiles(metadata); setSelected([]); }
    } catch (cause) {
      if (request === sequence.current) setError(cause instanceof Error ? cause.message : "字体状态读取失败");
    } finally { if (request === sequence.current) setLoading(false); }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    const requestSequence = sequence;
    return () => { mounted.current = false; requestSequence.current++; };
  }, [refresh]);

  const run = async (action: () => Promise<unknown>) => {
    if (operating.current) return false;
    operating.current = true;
    setBusy(true); setError(""); setRemoved(null);
    let success = false;
    try { await action(); success = true; }
    catch (cause) { if (mounted.current) setError(cause instanceof Error ? cause.message : "字体操作失败"); }
    finally {
      if (mounted.current) { await refresh(); if (mounted.current) { onChanged(); setBusy(false); } }
      operating.current = false;
    }
    return success;
  };

  const upload = async (file: File, existing?: ManagedFile | null) => {
    if (!/\.(ttf|otf|ttc)$/i.test(file.name) || !file.size || file.size > 32 * 1024 * 1024) {
      setError("请选择非空的 TTF、OTF 或 TTC 字体文件，最大 32 MiB");
      return false;
    }
    const success = await run(async () => {
      const encoded = await readUploadFile(file);
      await mutateManagedFile({ partition: "typst_fonts", name: existing?.name || file.name, operation: existing ? "replace" : "create", revision: existing?.revision, content_base64: encoded });
    });
    if (success && !existing && mounted.current) setTheme("__all__");
    return success;
  };

  const groups = status?.groups || [];
  const byName = new Map(files.map(file => [file.name, file]));
  const allNames = [...new Set([...groups.flatMap(group => group.required), ...(status?.missing || []), ...files.map(file => file.name)])];
  const required = groups.find(group => group.theme === theme)?.required || allNames;
  const rows: ManagedFontRow[] = required.map(name => ({ name, file: byName.get(name) || null, themes: groups.filter(group => group.required.includes(name)).map(group => group.theme) }));
  const visible = rows.filter(row => row.name.toLowerCase().includes(search.toLowerCase()) && (!format || row.name.toLowerCase().endsWith(`.${format}`)));
  return {
    status, files, groups, theme, search, format, selected, loading, busy, error, removed, downloadQueue, rows: visible,
    installed: rows.filter(row => row.file).length, required: required.length, missing: rows.filter(row => !row.file).length,
    refresh: async () => { setError(""); await refresh(); onChanged(); }, upload,
    download: (cdn: string) => status ? run(() => downloadQueue.download(cdn, status, theme === "__all__" ? undefined : theme)) : Promise.resolve(false),
    remove: (targets: ManagedFile[]) => run(async () => {
      const result = await deleteManagedFiles("typst_fonts", targets.map(file => ({ name: file.name, revision: file.revision })));
      if (mounted.current) setRemoved(result);
    }),
    setSelected,
    selectTheme: (value: string) => { setTheme(value); setSelected([]); },
    searchFonts: (value: string) => { setSearch(value); setSelected([]); },
    filterFormat: (value: string) => { setFormat(value); setSelected([]); },
  };
}
