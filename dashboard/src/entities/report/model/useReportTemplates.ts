import { useCallback, useEffect, useRef, useState } from "react";
import { fetchReportTemplates } from "../api/reportApi";
import type { ReportTemplateItem } from "./templates";

type RenderFormat = Parameters<typeof fetchReportTemplates>[0];

/** Load authoritative capabilities and discard results for an obsolete request. */
export function useReportTemplates(renderFormat: RenderFormat = "all", enabled = true) {
  const [result, setResult] = useState<{ format: RenderFormat; items: ReportTemplateItem[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const sequence = useRef(0);
  const refresh = useCallback(async () => {
    const request = ++sequence.current;
    setLoading(true);
    setResult(null);
    setError("");
    try {
      const items = await fetchReportTemplates(renderFormat);
      if (request === sequence.current) setResult({ format: renderFormat, items });
    } catch {
      if (request === sequence.current) setError("无法确认模板支持情况，请重试加载模板列表。");
    } finally {
      if (request === sequence.current) setLoading(false);
    }
  }, [renderFormat]);
  useEffect(() => {
    const pending = sequence;
    if (enabled) void refresh();
    return () => { pending.current++; };
  }, [enabled, refresh]);
  const ready = enabled && result?.format === renderFormat && !loading;
  return { templates: ready ? result.items : [], loading: enabled && (!result || loading) && !error, ready, error, refresh };
}
