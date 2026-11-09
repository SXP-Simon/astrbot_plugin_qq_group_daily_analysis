import { useEffect, useState } from "react";
import { fetchProviderList, type LLMProviderItem } from "@/entities/trace/api/traceApi";
import { useReportTemplates } from "@/entities/report/model/useReportTemplates";
import { formatTemplateOptions } from "@/entities/report/model/templates";

export function useResumeOptions(open: boolean) {
  const [providers, setProviders] = useState<LLMProviderItem[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(false);
  const [providerError, setProviderError] = useState("");
  const [providerRevision, setProviderRevision] = useState(0);
  const [selectedProvider, setSelectedProvider] = useState("auto");
  const [selectedTemplate, setSelectedTemplate] = useState("auto");
  const templates = useReportTemplates("configured", open);

  useEffect(() => {
    if (!open) return;
    setSelectedProvider("auto");
    setSelectedTemplate("auto");
  }, [open]);

  useEffect(() => {
    if (!open) return;
    let disposed = false;
    setLoadingProviders(true);
    setProviderError("");
    setProviders([]);
    fetchProviderList()
      .then((items) => {
        if (!disposed) setProviders(items);
      })
      .catch(() => {
        if (!disposed) setProviderError("模型列表暂时无法加载，可以重试或使用原配置。");
      })
      .finally(() => {
        if (!disposed) setLoadingProviders(false);
      });
    return () => {
      disposed = true;
    };
  }, [open, providerRevision]);

  const canConfirm =
    (selectedProvider === "auto" ||
      (!loadingProviders && providers.some((item) => item.id === selectedProvider))) &&
    (selectedTemplate === "auto" ||
      (templates.ready && templates.templates.some((item) => item.id === selectedTemplate)));

  return {
    providers,
    loadingProviders,
    providerError,
    retryProviders: () => setProviderRevision((revision) => revision + 1),
    selectedProvider,
    setSelectedProvider,
    selectedTemplate,
    setSelectedTemplate,
    canConfirm,
    templateOptions: formatTemplateOptions(templates.templates, true),
    loadingTemplates: templates.loading,
    templateError: templates.error,
    retryTemplates: templates.refresh,
  };
}
