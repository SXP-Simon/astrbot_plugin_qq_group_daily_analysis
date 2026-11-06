import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { rerenderReport } from "../../../entities/report/api/reportApi";
import type { ReportItem } from "../../../entities/report/model/types";
import { useReportTemplates } from "../../../entities/report/model/useReportTemplates";
import { formatTemplateOptions } from "../../../entities/report/model/templates";

export function useRerenderReport(
  open: boolean,
  report: ReportItem | null,
  onClose: () => void,
  onSuccess: () => void | Promise<unknown>,
) {
  const initialFormat =
    report?.is_html || /\.html?$/i.test(report?.filename ?? "") ? "html" : "image";
  const [renderFormat, setRenderFormat] = useState<"image" | "html">(initialFormat);
  const [selectedTemplate, setSelectedTemplate] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState("");
  const request = useRef<symbol | null>(null);
  const options = useReportTemplates(renderFormat, open && !!report);

  useEffect(() => {
    setRenderFormat(initialFormat);
    setSelectedTemplate("");
    setSubmitError("");
    setSubmitting(false);
    request.current = null;
    return () => {
      // 关闭、换报告或卸载后，旧请求不能关闭下一份报告的表单。
      request.current = null;
    };
  }, [open, report?.filename, report?.group_id, report?.platform, report?.trace_id, initialFormat]);

  const templateName =
    selectedTemplate ||
    options.templates.find((item) => item.id === "HatsuneMiku")?.id ||
    options.templates[0]?.id ||
    "";
  const validTemplate = options.ready && options.templates.some((item) => item.id === templateName);
  const canSubmit = !!report?.group_id?.trim() && validTemplate && !submitting;

  const submit = async () => {
    if (!open || !report || request.current || !canSubmit) return;
    const current = Symbol("重绘报告");
    request.current = current;
    setSubmitting(true);
    setSubmitError("");
    try {
      const result = await rerenderReport({
        group_id: report.group_id?.trim() ?? "",
        platform_id: report.platform ?? undefined,
        trace_id: report.trace_id ?? undefined,
        template_name: templateName,
        render_format: renderFormat,
      });
      if (request.current !== current) return;
      if (result?.success !== true || !result.filename?.trim())
        throw new Error("未收到新报告的生成结果，请刷新报告列表后确认。");
      toast.success("新报告已生成", { description: result.filename });
      onClose();
      // 生成成功与列表刷新是两件事，刷新失败不能让用户误以为需要再生成一次。
      try {
        await onSuccess();
      } catch {
        toast.warning("新报告已生成，列表未能更新。请手动刷新查看。");
      }
    } catch (error) {
      if (request.current === current)
        setSubmitError(error instanceof Error ? error.message : "重绘失败，请稍后重试。");
    } finally {
      if (request.current === current) {
        request.current = null;
        setSubmitting(false);
      }
    }
  };

  return {
    renderFormat,
    setRenderFormat: (value: "image" | "html") => {
      if (request.current) return;
      setRenderFormat(value);
      setSubmitError("");
    },
    templateName,
    setTemplateName: (value: string) => {
      if (request.current) return;
      setSelectedTemplate(value);
      setSubmitError("");
    },
    templateOptions: formatTemplateOptions(options.templates, false),
    loadingTemplates: options.loading,
    templatesReady: options.ready,
    templatesError: options.error,
    refreshTemplates: options.refresh,
    validTemplate,
    canSubmit,
    submitting,
    submitError,
    submit,
    close: () => {
      if (!request.current) onClose();
    },
  };
}
