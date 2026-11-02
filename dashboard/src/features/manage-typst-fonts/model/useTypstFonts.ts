import { useEffect, useRef, useState } from "react";
import { downloadTypstFonts, fetchTypstFonts } from "../../../entities/config/api/configApi";
import type { TypstFontStatus } from "../../../entities/config/model/typstFonts";

export function useTypstFonts(cdnBaseUrl: string) {
  const [status, setStatus] = useState<TypstFontStatus | null>(null);
  const [loading, setLoading] = useState(false);
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

  const run = async (download: boolean) => {
    if (loading) return;
    const request = ++sequence.current;
    setLoading(true);
    setError("");
    try {
      const value = download ? await downloadTypstFonts(cdnBaseUrl) : await fetchTypstFonts();
      if (sequence.current === request) setStatus(value);
    } catch (cause: unknown) {
      if (sequence.current === request) setError(cause instanceof Error ? cause.message : "字体操作未完成，请重试。");
    } finally {
      if (sequence.current === request) setLoading(false);
    }
  };
  return { status, loading, error, run };
}
