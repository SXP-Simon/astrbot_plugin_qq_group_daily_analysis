import { useEffect, useState } from "react";
import { fetchTemplatePreview } from "../api/reportApi";
import { getReportTemplatePreviewUrl } from "./templates";

/** 自定义图片经插件读取；内置示例沿用所选 CDN，切换时不展示旧模板。 */
export function useTemplatePreview(
  templateId: string,
  isCustom: boolean,
  cdnBaseUrl: string | null,
  enabled = true,
) {
  const [result, setResult] = useState<{ id: string; src: string | null; error: string } | null>(
    null,
  );
  useEffect(() => {
    if (!enabled || !isCustom || !templateId) return;
    let active = true;
    setResult(null);
    void fetchTemplatePreview(templateId)
      .then((src) => {
        if (active)
          setResult({ id: templateId, src, error: src ? "" : "此模板没有可用的预览图片。" });
      })
      .catch(() => {
        if (active)
          setResult({ id: templateId, src: null, error: "预览图片读取失败，请重新打开后再试。" });
      });
    return () => {
      active = false;
    };
  }, [enabled, isCustom, templateId]);
  if (!enabled || !templateId) return { src: null, loading: false, error: "" };
  if (!isCustom)
    return {
      src: getReportTemplatePreviewUrl(templateId, cdnBaseUrl) ?? null,
      loading: false,
      error: cdnBaseUrl === null ? "CDN 地址无效，请先修改图片渲染策略。" : "",
    };
  const current = result?.id === templateId ? result : null;
  return { src: current?.src ?? null, loading: !current, error: current?.error ?? "" };
}
