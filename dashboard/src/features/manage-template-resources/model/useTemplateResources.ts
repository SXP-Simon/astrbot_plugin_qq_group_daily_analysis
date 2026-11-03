import { useCallback, useEffect, useRef, useState } from "react";
import { downloadTemplateResource, fetchTemplateResources } from "../../../entities/config/api/templateResourceApi";
import { cdnBaseUrlSchema } from "../../../entities/config/model/renderingConfig";
import type { TemplateResourceStatus } from "../../../entities/config/model/templateResources";

export function useTemplateResources(cdnBaseUrl: string, refreshVersion = 0) {
  const [status, setStatus] = useState<TemplateResourceStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [progress, setProgress] = useState({ done: 0, total: 0, failed: [] as { name: string; message: string }[] });
  const mounted = useRef(false);
  const busy = useRef(false);
  const refreshSequence = useRef(0);

  const refresh = useCallback(async () => {
    if (busy.current) return;
    const sequence = ++refreshSequence.current;
    setLoading(true);
    setError("");
    try {
      const value = await fetchTemplateResources();
      if (mounted.current && refreshSequence.current === sequence) setStatus(value);
    } catch (cause: unknown) {
      if (mounted.current && refreshSequence.current === sequence) setError(cause instanceof Error ? cause.message : "素材状态读取失败，请重试。");
    } finally {
      if (mounted.current && refreshSequence.current === sequence) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mounted.current = true;
    void refresh();
    return () => { mounted.current = false; refreshSequence.current += 1; };
  }, [refresh]);
  useEffect(() => { if (refreshVersion > 0) void refresh(); }, [refreshVersion, refresh]);

  const download = async (theme?: string) => {
    if (!status || busy.current) return;
    const cdn = cdnBaseUrlSchema.safeParse(cdnBaseUrl);
    if (!cdn.success) { setError(cdn.error.issues[0].message); return; }
    const queue = status.groups.filter((group) => !theme || group.theme === theme)
      .flatMap((group) => group.files.filter((file) => !file.available));
    if (!queue.length) return;
    busy.current = true;
    setRunning(true);
    setError("");
    setProgress({ done: 0, total: queue.length, failed: [] });
    // 请求粒度是单文件；最多三个并发，关闭页面后不再发起剩余下载。
    const worker = async () => {
      while (mounted.current && queue.length) {
        const file = queue.shift();
        if (!file) return;
        try {
          await downloadTemplateResource(file.name, cdn.data);
          if (mounted.current) setStatus((current) => current && ({ ...current, groups: current.groups.map((group) => ({
            ...group, files: group.files.map((item) => item.name === file.name ? { ...item, available: true } : item),
          })) }));
        } catch (cause: unknown) {
          if (mounted.current) setProgress((value) => ({ ...value, failed: [...value.failed, {
            name: file.name, message: cause instanceof Error ? cause.message : "下载失败，请重试",
          }] }));
        } finally {
          if (mounted.current) setProgress((value) => ({ ...value, done: value.done + 1 }));
        }
      }
    };
    try { await Promise.all([worker(), worker(), worker()]); }
    finally { busy.current = false; if (mounted.current) setRunning(false); }
  };

  return { status, loading, running, error, progress, refresh, download };
}
