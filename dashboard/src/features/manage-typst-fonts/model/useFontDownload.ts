import { DownloadBatch } from "../../../entities/config/api/downloadBatch";
import { useEffect, useRef, useState } from "react";
import { downloadTypstFonts, fetchTypstFonts, fetchFontDownloadProgress } from "../../../entities/config/api/configApi";
import { cdnBaseUrlSchema } from "../../../entities/config/model/renderingConfig";
import type { FontDownloadSource, FontTransfer, TypstFontStatus } from "../../../entities/config/model/typstFonts";

export function useFontDownload(onStatus: (status: TypstFontStatus) => void) {
  const [progress, setProgress] = useState({ done: 0, total: 0, current: "", failed: [] as { name: string; message: string }[] });
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [source, setSource] = useState<FontDownloadSource>("cdn");
  const [transfer, setTransfer] = useState<FontTransfer | null>(null);
  const [progressError, setProgressError] = useState("");
  const mounted = useRef(false);
  const busy = useRef(false);
  const batch = useRef(new DownloadBatch());
  const [cancelled, setCancelled] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const cancel = async () => {
    setCancelled(true); setCancelling(true);
    try { await batch.current.cancel(); }
    catch (cause) { if (mounted.current) setError(cause instanceof Error ? cause.message : "取消未确认，请重试"); }
    finally { if (mounted.current) setCancelling(false); }
  };
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; void batch.current.cancel().catch(() => {}); };
  }, []);

  const download = async (cdnBaseUrl: string, status: TypstFontStatus, theme?: string) => {
    if (busy.current) return;
    const cdn = cdnBaseUrlSchema.safeParse(source === "github" ? "" : cdnBaseUrl);
    if (!cdn.success) { setError(cdn.error.issues[0].message); return; }
    const group = status.groups?.find(item => item.theme === theme);
    if (theme && !group) { setError("模板字体清单已变化，请刷新状态后重试。"); return; }
    const queue = [...new Set(theme ? group?.missing || [] : status.missing)];
    batch.current = new DownloadBatch();
    setCancelled(false);
    busy.current = true;
    setRunning(true); setError("");
    setProgress({ done: 0, total: queue.length, current: "", failed: [] });
    try {
      // 每个请求只下载一个字体，取消后立即停止后续队列。
      for (const name of queue) {
        if (!mounted.current || batch.current.stopped) break;
        setProgress(value => ({ ...value, current: name }));
        setTransfer(null); setProgressError("");
        try {
          const value = await batch.current.run(async id => {
            let active = true;
            let timer: ReturnType<typeof setTimeout>;
            // 按请求读取真实字节数；不重叠轮询，也不让旧文件的迟到响应覆盖下一份。
            const poll = async () => {
              try {
                const snapshot = await fetchFontDownloadProgress(id);
                if (active && mounted.current) { setTransfer(snapshot); setProgressError(""); }
              } catch {
                if (active && mounted.current) setProgressError("进度暂时读取失败，下载可能仍在继续；可以取消或等待结果。");
              }
              if (active && mounted.current) timer = setTimeout(() => void poll(), 1000);
            };
            timer = setTimeout(() => void poll(), 500);
            try { return await downloadTypstFonts(cdn.data, theme, name, id, source); }
            finally { active = false; clearTimeout(timer); }
          });
          if (mounted.current) { onStatus(value); setProgress(value => ({ ...value, done: value.done + 1 })); }
        } catch (cause) {
          if (mounted.current && !batch.current.stopped) setProgress(value => ({ ...value, done: value.done + 1, failed: [...value.failed, { name, message: cause instanceof Error ? cause.message : "字体下载失败，请检查实际来源与服务器网络" }] }));
        }
      }
      if (mounted.current) {
        try { const value = await fetchTypstFonts(); if (mounted.current) onStatus(value); }
        catch { if (mounted.current) setError("下载请求已结束，但最新字体状态读取失败，请刷新确认。"); }
      }
    } finally {
      busy.current = false;
      if (mounted.current) { setRunning(false); setTransfer(null); setProgressError(""); setProgress(value => ({ ...value, current: "" })); }
    }
  };
  return { progress, running, error, download, cancel, cancelled, cancelling, source, setSource, transfer, progressError };
}
