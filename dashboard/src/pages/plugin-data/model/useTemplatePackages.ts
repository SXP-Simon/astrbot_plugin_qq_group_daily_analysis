import { useCallback, useEffect, useRef, useState } from "react";
import { fetchReportTemplates, uninstallTemplate } from "../../../entities/report/api/reportApi";
import type { ReportTemplateItem } from "../../../entities/report/model/templates";
import type { ManagedFileGroup } from "../../../entities/plugin-data/api/managedFilesApi";

export function useTemplatePackages(groups: ManagedFileGroup[], onChanged: () => void) {
  const [templates, setTemplates] = useState<ReportTemplateItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const sequence = useRef(0);
  const operating = useRef(false);
  const refresh = useCallback(async () => {
    const request = ++sequence.current;
    setLoading(true); setError("");
    try {
      const items = await fetchReportTemplates();
      if (sequence.current === request) setTemplates(items.filter(item => item.is_custom));
    } catch (cause) { if (sequence.current === request) setError(cause instanceof Error ? cause.message : "模板信息读取失败"); }
    finally { if (sequence.current === request) setLoading(false); }
  }, []);
  const groupSignature = groups.map(group => `${group.directory}:${group.count}:${group.size_bytes}`).join("|");
  useEffect(() => { const ref = sequence; void refresh(); return () => { ref.current++; }; }, [refresh, groupSignature]);
  const rows = groups.map(group => ({ ...group, template: templates.find(item => item.id === group.directory) }))
    .sort((a, b) => Number(!!b.template) - Number(!!a.template) || a.directory.localeCompare(b.directory));
  return { rows, loading, busy, error, refresh,
    uninstall: async (name: string) => {
      if (operating.current) return false;
      operating.current = true; setBusy(name); setError("");
      try { await uninstallTemplate(name); onChanged(); await refresh(); return true; }
      catch (cause) { setError(cause instanceof Error ? cause.message : "模板移除失败"); return false; }
      finally { operating.current = false; setBusy(""); }
    },
  };
}
