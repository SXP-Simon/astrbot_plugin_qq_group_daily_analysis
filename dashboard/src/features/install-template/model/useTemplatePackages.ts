import { useCallback, useEffect, useRef, useState } from "react";
import { fetchReportTemplates, uninstallTemplate } from "../../../entities/report/api/reportApi";
import type { ReportTemplateItem } from "../../../entities/report/model/templates";
import type { ManagedFileGroup } from "../../../entities/plugin-data/api/managedFilesApi";

export function useTemplatePackages(groups: ManagedFileGroup[], onChanged: () => void) {
  const [templates, setTemplates] = useState<ReportTemplateItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const lifecycle = useRef(0);
  useEffect(() => {
    const epoch = lifecycle;
    epoch.current++;
    return () => {
      epoch.current++;
    };
  }, []);
  const sequence = useRef(0);
  const operating = useRef(false);
  const refresh = useCallback(async () => {
    const request = ++sequence.current;
    setLoading(true);
    setError("");
    try {
      const items = await fetchReportTemplates();
      if (sequence.current === request) setTemplates(items.filter((item) => item.is_custom));
    } catch (cause) {
      if (sequence.current === request)
        setError(cause instanceof Error ? cause.message : "模板信息读取失败");
    } finally {
      if (sequence.current === request) setLoading(false);
    }
  }, []);
  const groupSignature = groups
    .map((group) => `${group.directory}:${group.count}:${group.size_bytes}`)
    .join("|");
  useEffect(() => {
    const ref = sequence;
    void refresh();
    return () => {
      ref.current++;
    };
  }, [refresh, groupSignature]);
  const rows = groups
    .map((group) => ({ ...group, template: templates.find((item) => item.id === group.directory) }))
    .sort(
      (a, b) =>
        Number(!!b.template) - Number(!!a.template) || a.directory.localeCompare(b.directory),
    );
  return {
    rows,
    loading,
    busy,
    error,
    actionError,
    clearActionError: () => setActionError(""),
    refresh,
    uninstall: async (name: string) => {
      if (operating.current) return false;
      if (name === "." || !groups.some((group) => group.directory === name)) {
        setActionError("模板目录已变化，请刷新后重新选择。");
        return false;
      }
      const request = lifecycle.current;
      operating.current = true;
      setBusy(name);
      setActionError("");
      try {
        const result = await uninstallTemplate(name);
        if (request !== lifecycle.current) return false;
        if (!result || result.name !== name || result.removed !== true)
          throw new Error("模板未移除，请刷新后重试。");
        onChanged();
        if (request !== lifecycle.current) return false;
        await refresh();
        return request === lifecycle.current;
      } catch (cause) {
        if (request === lifecycle.current)
          setActionError(cause instanceof Error ? cause.message : "模板移除失败");
        return false;
      } finally {
        if (request === lifecycle.current) {
          operating.current = false;
          setBusy("");
        }
      }
    },
  };
}
