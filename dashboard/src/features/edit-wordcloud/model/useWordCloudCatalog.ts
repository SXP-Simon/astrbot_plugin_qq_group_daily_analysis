import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchWordCloudCatalog } from "../../../entities/wordcloud/api/wordCloudApi";
import { DEFAULT_WORDCLOUD_OPTIONS, type WordCloudCatalog } from "../../../entities/wordcloud/model/types";

interface WordCloudCatalogParams {
  active: boolean;
  template?: string;
  font?: string;
  revision?: number;
}

export interface WordCloudCatalogOption {
  value: string;
  label: string;
}

const FALLBACK_CATALOG: WordCloudCatalog = {
  templates: [{ name: "ATRI", label: "亚托莉 (ATRI)" }],
  fonts: [
    { id: "wenkai", label: "霞鹜文楷" },
    { id: "sans", label: "无衬线" },
    { id: "serif", label: "衬线" },
  ],
};

export function useWordCloudCatalog({
  active,
  template = DEFAULT_WORDCLOUD_OPTIONS.template,
  font = DEFAULT_WORDCLOUD_OPTIONS.font,
  revision = 0,
}: WordCloudCatalogParams) {
  const [catalog, setCatalog] = useState<WordCloudCatalog | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [refreshIndex, setRefreshIndex] = useState(0);
  const refresh = useCallback(() => setRefreshIndex((current) => current + 1), []);

  useEffect(() => {
    if (!active) {
      setLoading(false);
      return;
    }
    let current = true;
    setLoading(true);
    setError("");
    fetchWordCloudCatalog().then((result) => {
      if (current) setCatalog(result);
    }).catch((reason: unknown) => {
      if (current) setError(reason instanceof Error ? reason.message : "读取词云模板和字体失败，请重试");
    }).finally(() => {
      if (current) setLoading(false);
    });
    return () => { current = false; };
  }, [active, revision, refreshIndex]);

  const options = useMemo(() => {
    const source = catalog ?? FALLBACK_CATALOG;
    const templateOptions: WordCloudCatalogOption[] = source.templates.map((item) => ({ value: item.name, label: item.label }));
    const fontOptions: WordCloudCatalogOption[] = source.fonts.map((item) => ({ value: item.id, label: item.label }));
    // 目录暂不可用或文件已移除时仍保留已配置值，不因打开设置页改写配置。
    if (!templateOptions.some((item) => item.value === template)) {
      templateOptions.push({ value: template, label: `${template || "空值"}（当前配置，目录中未找到）` });
    }
    if (!fontOptions.some((item) => item.value === font)) {
      fontOptions.push({ value: font, label: `${font || "空值"}（当前配置，目录中未找到）` });
    }
    return { templateOptions, fontOptions };
  }, [catalog, template, font]);

  return { ...options, loading, error, refresh };
}
