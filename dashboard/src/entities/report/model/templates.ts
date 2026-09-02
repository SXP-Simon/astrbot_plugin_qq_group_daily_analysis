export interface ReportTemplateItem {
  id: string;
  label: string;
  is_custom?: boolean;
  has_image?: boolean;
  has_html?: boolean;
  can_uninstall?: boolean;
}

export interface SelectOptionItem {
  label: string;
  value: string;
  is_custom?: boolean;
}

export interface TemplateVisualInfo {
  key: string;
  name: string;
  desc: string;
  tag: string;
  tagColor: string;
}

export const KNOWN_TEMPLATES: TemplateVisualInfo[] = [
  {
    key: "scrapbook",
    name: "Scrapbook (默认手账)",
    desc: "手账贴纸风格，丰富拼贴与涂鸦设计，温馨可爱",
    tag: "默认手账",
    tagColor: "orange",
  },
  {
    key: "ATRI",
    name: "ATRI (亚托莉)",
    desc: "《ATRI -My Dear Moments-》水下与海洋蓝调风格",
    tag: "水下海洋",
    tagColor: "blue",
  },
  {
    key: "BlueArchive",
    name: "BlueArchive (蔚蓝档案)",
    desc: "碧蓝档案 UI 风格，清爽明亮青蓝与现代科技感",
    tag: "清爽科技",
    tagColor: "cyan",
  },
  {
    key: "HatsuneMiku",
    name: "HatsuneMiku (初音未来)",
    desc: "初音未来葱绿配色与音乐律动设计",
    tag: "葱绿音乐",
    tagColor: "green",
  },
  {
    key: "retro_futurism",
    name: "Retro Futurism (复古未来)",
    desc: "复古未来主义与像素霓虹排版风格",
    tag: "复古像素",
    tagColor: "purple",
  },
  {
    key: "hack",
    name: "Hack (黑客终端)",
    desc: "赛博朋克极客终端，深黑背景与荧光绿代码风",
    tag: "黑客极客",
    tagColor: "lime",
  },
  {
    key: "spring_festival",
    name: "Spring Festival (新春红)",
    desc: "中国传统喜庆红金配色，新春佳节喜气洋洋",
    tag: "新春年节",
    tagColor: "red",
  },
  {
    key: "simple",
    name: "Simple (极简浅色)",
    desc: "干净清爽极简留白风格，高信息密度与易读性",
    tag: "极简素雅",
    tagColor: "default",
  },
  {
    key: "format",
    name: "Format (标准卡片)",
    desc: "标准规范报表卡片，商务整洁",
    tag: "标准报表",
    tagColor: "geekblue",
  },
];

export function getTemplateCdnUrl(templateKey: string): string {
  return `https://fastly.jsdelivr.net/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/${templateKey}-demo.jpg`;
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
  { id: "format", label: "标准卡片 (Format)", is_custom: false },
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
