import { useEffect, useRef, useState } from "react";
import { fetchTypstFonts } from "../../../entities/config/api/configApi";
import type { TypstFontStatus } from "../../../entities/config/model/typstFonts";

import { useFontDownload } from "./useFontDownload";

export function useTypstFonts(cdnBaseUrl: string) {
  const [status, setStatus] = useState<TypstFontStatus | null>(null);
  const [operation, setOperation] = useState<"selected" | "all" | "refresh" | null>(null);
  const downloadQueue = useFontDownload(setStatus);
  const loading = operation !== null || downloadQueue.running;
  const [error, setError] = useState("");
  const sequence = useRef(0);

  useEffect(() => {
    const request = ++sequence.current;
    void fetchTypstFonts().then((value) => {
      if (sequence.current === request) setStatus(value);
    }).catch((cause: unknown) => {
      if (sequence.current === request) setError(cause instanceof Error ? cause.message : "字体状态读取失败");
    });
    return () => { sequence.current += 1; };
  }, []);

  const run = async (download: boolean, theme?: string) => {
    if (loading) return;
    const request = ++sequence.current;
    setOperation(download ? theme === undefined ? "all" : "selected" : "refresh");
    setError("");
    try {
      if (download && status) await downloadQueue.download(cdnBaseUrl, status, theme);
      else {
        const value = await fetchTypstFonts();
        if (sequence.current === request) setStatus(value);
      }
    } catch (cause: unknown) {
      if (sequence.current === request) setError(cause instanceof Error ? cause.message : "字体操作未完成，请重试。");
      if (download) {
        const partial = await fetchTypstFonts().catch(() => null);
        if (partial && sequence.current === request) setStatus(partial);
      }
    } finally {
      if (sequence.current === request) setOperation(null);
    }
  };
  return { status, loading, operation, error, run, downloadQueue };
}
