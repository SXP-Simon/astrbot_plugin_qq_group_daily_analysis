import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { fetchReportTemplates, uninstallTemplate } from "@/entities/report/api/reportApi";
import type { ReportTemplateItem } from "@/entities/report/model/templates";

export function useTemplateRemoval(
  open: boolean,
  onClose: () => void,
  onUninstalled?: (name: string) => void,
) {
  const [templates, setTemplates] = useState<ReportTemplateItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [actionError, setActionError] = useState("");
  const [target, setTarget] = useState<ReportTemplateItem | null>(null);
  const sequence = useRef(0),
    epoch = useRef(0),
    pending = useRef(false),
    visible = useRef(open);
  visible.current = open;
  const refresh = useCallback(async () => {
    if (!visible.current) return;
    const request = ++sequence.current;
    setLoading(true);
    setError("");
    try {
      const items = await fetchReportTemplates();
      if (request === sequence.current && visible.current)
        setTemplates(items.filter((item) => item.can_uninstall === true));
    } catch (cause) {
      if (request === sequence.current && visible.current)
        setError(cause instanceof Error ? cause.message : "模板列表读取失败，请重试。");
    } finally {
      if (request === sequence.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    const lifecycle = epoch,
      lists = sequence;
    lifecycle.current++;
    pending.current = false;
    setBusy(false);
    setTarget(null);
    setActionError("");
    setTemplates([]);
    setError("");
    setLoading(false);
    if (open) void refresh();
    return () => {
      lifecycle.current++;
      lists.current++;
    };
  }, [open, refresh]);
  return {
    templates,
    loading,
    busy,
    error,
    actionError,
    target,
    refresh,
    close: () => {
      if (!pending.current) onClose();
    },
    select: (item: ReportTemplateItem | null) => {
      if (!pending.current) {
        setTarget(item);
        setActionError("");
      }
    },
    remove: async () => {
      if (!target || pending.current || !visible.current) return;
      const request = epoch.current,
        name = target.id;
      pending.current = true;
      setBusy(true);
      setActionError("");
      try {
        const result = await uninstallTemplate(name);
        if (request !== epoch.current || !visible.current) return;
        if (!result || !result.removed || result.name !== name)
          throw new Error("模板未移除，请刷新后重试。");
        setTarget(null);
        setTemplates((current) => current.filter((item) => item.id !== name));
        toast.success(`模板已卸载：${name}`);
        onUninstalled?.(name);
        await refresh();
      } catch (cause) {
        if (request === epoch.current && visible.current)
          setActionError(cause instanceof Error ? cause.message : "移除失败，请重试。");
      } finally {
        if (request === epoch.current) {
          pending.current = false;
          setBusy(false);
        }
      }
    },
  };
}
