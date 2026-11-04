import { useEffect, useRef, useState } from "react";
import { DownloadBatch } from "../../../entities/config/api/downloadBatch";
import { startManagedUpload, uploadManagedChunk, type ManagedFile } from "../../../entities/plugin-data/api/managedFilesApi";

interface FontUploadProgress {
  name: string;
  total: number;
  received: number;
  phase: "uploading" | "saved" | "cancelled" | "failed";
  error?: string;
}

/** 每次只传递 1 MiB，进度使用服务器回执，取消会清理暂存并拒绝迟到分块。 */
export function useFontUpload(onSaved: () => void) {
  const [progress, setProgress] = useState<FontUploadProgress | null>(null);
  const [elapsed, setElapsed] = useState(0);
  const [cancelling, setCancelling] = useState(false);
  const active = useRef<DownloadBatch | null>(null);
  const mounted = useRef(true);
  const running = progress?.phase === "uploading";
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; void active.current?.cancel().catch(() => {}); };
  }, []);
  useEffect(() => {
    if (!running) return;
    const started = Date.now();
    const timer = setInterval(() => setElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [running]);

  const cancel = async () => {
    if (!active.current) return;
    setCancelling(true);
    try { await active.current.cancel(); }
    catch (cause) { if (mounted.current) setProgress(value => value && ({ ...value, error: cause instanceof Error ? cause.message : "取消未确认，请重试" })); }
    finally { if (mounted.current) setCancelling(false); }
  };

  const upload = async (file: File, name: string, existing?: ManagedFile | null) => {
    if (active.current) return false;
    const batch = new DownloadBatch("plugin-data/files/upload/cancel");
    active.current = batch;
    setElapsed(0);
    setProgress({ name, total: file.size, received: 0, phase: "uploading" });
    let wasCancelled = false;
    let cleanup = "";
    try {
      await batch.run(async id => {
        try {
          await startManagedUpload({ download_id: id, partition: "typst_fonts", name, operation: existing ? "replace" : "create", revision: existing?.revision || "", total: file.size });
          for (let offset = 0; offset < file.size; offset += 1024 * 1024) {
            if (batch.stopped) throw new Error("上传已取消");
            const chunk = new File([file.slice(offset, offset + 1024 * 1024)], file.name, { type: file.type });
            const receipt = await uploadManagedChunk(chunk, id, offset);
            if (receipt.received !== offset + chunk.size || receipt.total !== file.size || receipt.complete !== (receipt.received === file.size)) {
              throw new Error("服务器上传回执不匹配，请刷新字体状态后重试。");
            }
            if (mounted.current) setProgress({ name, total: file.size, received: receipt.received, phase: receipt.complete ? "saved" : "uploading" });
          }
        } catch (cause) {
          wasCancelled = batch.stopped;
          // 必须在 run 释放请求标识前取消，网络失败也要清理服务器暂存。
          try { await batch.cancel(); } catch { cleanup = "；暂存清理尚未确认，闲置暂存会在后续上传时清理，请刷新字体状态后重试"; }
          throw cause;
        }
      });
      if (mounted.current) onSaved();
      return true;
    } catch (cause) {
      if (mounted.current) {
        setProgress(value => value && ({ ...value, phase: wasCancelled && !cleanup ? "cancelled" : "failed", error: `${cause instanceof Error ? cause.message : "上传失败"}${cleanup}` }));
        onSaved();
      }
      return false;
    } finally { active.current = null; if (mounted.current) setCancelling(false); }
  };
  return { progress, elapsed, running, cancelling, upload, cancel };
}
