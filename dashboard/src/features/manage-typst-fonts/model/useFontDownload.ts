import { useEffect, useRef, useState } from "react";
import { downloadTypstFonts, fetchTypstFonts } from "../../../entities/config/api/configApi";
import { cdnBaseUrlSchema } from "../../../entities/config/model/renderingConfig";
import type { TypstFontStatus } from "../../../entities/config/model/typstFonts";

export function useFontDownload(onStatus: (status: TypstFontStatus) => void) {
  const [progress, setProgress] = useState({ done: 0, total: 0, current: "", failed: [] as { name: string; message: string }[] });
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const mounted = useRef(false);
  const busy = useRef(false);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  const download = async (cdnBaseUrl: string, status: TypstFontStatus, theme?: string) => {
    if (busy.current) return;
    const cdn = cdnBaseUrlSchema.safeParse(cdnBaseUrl);
    if (!cdn.success) { setError(cdn.error.issues[0].message); return; }
    const group = status.groups?.find(item => item.theme === theme);
    if (theme && !group) { setError("模板字体清单已变化，请刷新状态后重试。"); return; }
    const queue = [...new Set(theme ? group?.missing || [] : status.missing)];
    busy.current = true;
    setRunning(true); setError("");
    setProgress({ done: 0, total: queue.length, current: "", failed: [] });
    try {
      // The server serializes font writes; one file per request exposes real completion.
      for (const name of queue) {
        if (!mounted.current) break;
        setProgress(value => ({ ...value, current: name }));
        try {
          const value = await downloadTypstFonts(cdn.data, theme, name);
          if (mounted.current) onStatus(value);
        } catch (cause) {
          if (mounted.current) setProgress(value => ({ ...value, failed: [...value.failed, { name, message: cause instanceof Error ? cause.message : "字体下载失败，请更换 CDN 后重试" }] }));
        } finally {
          if (mounted.current) setProgress(value => ({ ...value, done: value.done + 1 }));
        }
      }
      if (mounted.current) {
        try { const value = await fetchTypstFonts(); if (mounted.current) onStatus(value); }
        catch { if (mounted.current) setError("下载请求已结束，但最新字体状态读取失败，请刷新确认。"); }
      }
    } finally {
      busy.current = false;
      if (mounted.current) { setRunning(false); setProgress(value => ({ ...value, current: "" })); }
    }
  };
  return { progress, running, error, download };
}
