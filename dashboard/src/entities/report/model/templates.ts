export interface ReportTemplateItem {
  id: string;
  label: string;
  is_custom?: boolean;
  has_image?: boolean;
  has_html?: boolean;
}

export interface SelectOptionItem {
  label: string;
  value: string;
  is_custom?: boolean;
}

export const DEFAULT_REPORT_TEMPLATES: ReportTemplateItem[] = [
  { id: "scrapbook", label: "手账风格 (Scrapbook / 默认)", is_custom: false },
  { id: "ATRI", label: "亚托莉 (ATRI)", is_custom: false },
  { id: "HatsuneMiku", label: "初音未来 (HatsuneMiku)", is_custom: false },
  { id: "spring_festival", label: "新春佳节 (Spring Festival)", is_custom: false },
  { id: "retro_futurism", label: "复古未来 (Retro Futurism)", is_custom: false },
  { id: "hack", label: "黑客赛博 (Hack)", is_custom: false },
  { id: "BlueArchive", label: "蔚蓝档案 (BlueArchive)", is_custom: false },
  { id: "simple", label: "极简黑白 (Simple)", is_custom: false },
];

export function formatTemplateOptions(
  templates: ReportTemplateItem[],
  includeAuto = false
): SelectOptionItem[] {
  const list = templates && templates.length > 0 ? templates : DEFAULT_REPORT_TEMPLATES;
  const options: SelectOptionItem[] = list.map((t) => ({
    label: t.label || `${t.id}${t.is_custom ? " (自定义)" : ""}`,
    value: t.id,
    is_custom: Boolean(t.is_custom),
  }));

  if (includeAuto) {
    return [{ label: "跟随系统默认配置 (推荐)", value: "auto" }, ...options];
  }
  return options;
}
