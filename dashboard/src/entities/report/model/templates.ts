export interface ReportTemplateItem {
  id: string;
  label: string;
  is_custom?: boolean;
  has_image?: boolean;
  has_html?: boolean;
  has_typst?: boolean;
  can_uninstall?: boolean;
  display_name?: string;
  desc?: string;
  tag?: string;
  tag_color?: string;
}

export interface TemplateRequirements {
  engine: "typst" | "html";
  formats: readonly string[];
}

/** 只有实际入口支持当前引擎与全部输出格式时才允许选择。 */
export function supportsTemplate(
  template: ReportTemplateItem,
  requirements?: TemplateRequirements,
): boolean {
  if (!requirements) return true;
  if (requirements.formats.includes("html") && !(template.has_html || template.has_image))
    return false;
  if (!requirements.formats.includes("image")) return true;
  return requirements.engine === "typst"
    ? template.has_typst === true
    : template.has_image === true;
}

export function templateCapabilities(template: ReportTemplateItem): string[] {
  return [
    template.has_image ? "HTML 图片" : "",
    template.has_html ? "HTML 网页" : "",
    template.has_typst ? "Typst 图片" : "",
  ].filter(Boolean);
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
    key: "HatsuneMiku",
    name: "HatsuneMiku (初音未来 / 默认)",
    desc: "初音未来葱绿配色与音乐律动设计，支持多语言动态自适应",
    tag: "默认主题",
    tagColor: "green",
  },
  {
    key: "scrapbook",
    name: "Scrapbook (手账风格)",
    desc: "手账贴纸风格，丰富拼贴与涂鸦设计，温馨可爱",
    tag: "手账贴纸",
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
    key: "art_nouveau",
    name: "Art Nouveau (新艺术运动)",
    desc: "源自19世纪末穆夏海报与自然美学，以流动藤蔓、雅金边框与典雅衬线排版呈现自然与艺术的和谐",
    tag: "新艺术风",
    tagColor: "gold",
  },
  {
    key: "deepseek_maid",
    name: "DeepSeek 鲸鱼女仆娘",
    desc: "大肥鱼打工实录：饭票账单、内心OS、摸鱼雷达与DeepSleep交班",
    tag: "蓝白女仆",
    tagColor: "blue",
  },
  {
    key: "maria",
    name: "Maria (圣母在上 · 山百合会)",
    desc: "私立莉莉安女子学园山百合会风格，典雅蔷薇纹样、法文花体与复古羊皮纸信札质感",
    tag: "圣母在上",
    tagColor: "magenta",
  },
  {
    key: "format",
    name: "Format (标准卡片)",
    desc: "标准规范报表卡片，商务整洁",
    tag: "标准报表",
    tagColor: "geekblue",
  },
];

export const GITHUB_REPO_OWNER = "SXP-Simon";
export const GITHUB_REPO_NAME = "astrbot_plugin_qq_group_daily_analysis";
export const GITHUB_REPO_BRANCH = "main";
export function getTemplateCdnUrl(
  templateKey: string,
  cdnBaseUrl: string | null,
): string | undefined {
  if (cdnBaseUrl === null) return undefined;
  return `${cdnBaseUrl}/gh/${GITHUB_REPO_OWNER}/${GITHUB_REPO_NAME}@${GITHUB_REPO_BRANCH}/assets/${templateKey}-demo.webp`;
}

export const DEFAULT_REPORT_TEMPLATES: ReportTemplateItem[] = [
  {
    id: "HatsuneMiku",
    label: "初音未来 (HatsuneMiku / 默认)",
    is_custom: false,
    has_image: true,
    has_html: true,
    has_typst: true,
  },
  {
    id: "scrapbook",
    label: "手账风格 (Scrapbook)",
    is_custom: false,
    has_image: true,
    has_html: true,
    has_typst: true,
  },
  {
    id: "ATRI",
    label: "亚托莉 (ATRI)",
    is_custom: false,
    has_image: true,
    has_html: true,
    has_typst: true,
  },
  {
    id: "spring_festival",
    label: "新春佳节 (Spring Festival)",
    is_custom: false,
    has_image: true,
    has_html: true,
    has_typst: true,
  },
  {
    id: "retro_futurism",
    label: "复古未来 (Retro Futurism)",
    is_custom: false,
    has_image: true,
    has_html: true,
    has_typst: true,
  },
  {
    id: "hack",
    label: "黑客赛博 (Hack)",
    is_custom: false,
    has_image: true,
    has_html: true,
    has_typst: true,
  },
  {
    id: "BlueArchive",
    label: "蔚蓝档案 (BlueArchive)",
    is_custom: false,
    has_image: true,
    has_html: true,
    has_typst: true,
  },
  {
    id: "simple",
    label: "极简黑白 (Simple)",
    is_custom: false,
    has_image: true,
    has_html: true,
    has_typst: true,
  },
  {
    id: "art_nouveau",
    label: "新艺术运动 (Art Nouveau)",
    is_custom: false,
    has_image: true,
    has_html: true,
    has_typst: true,
  },
  {
    id: "deepseek_maid",
    label: "DeepSeek 鲸鱼女仆娘",
    is_custom: false,
    has_image: true,
    has_html: true,
    has_typst: true,
  },
  {
    id: "maria",
    label: "圣母在上 (Maria)",
    is_custom: false,
    has_image: true,
    has_html: true,
    has_typst: true,
  },
  {
    id: "format",
    label: "标准卡片 (Format)",
    is_custom: false,
    has_image: true,
    has_html: true,
    has_typst: true,
  },
];

export function formatTemplateOptions(
  templates: ReportTemplateItem[],
  includeAuto = false,
): SelectOptionItem[] {
  const list = templates;
  const options: SelectOptionItem[] = list.map((t) => ({
    label: `${t.label || t.id}${templateCapabilities(t).length ? ` [${templateCapabilities(t).join(" / ")}]` : ""}`,
    value: t.id,
    is_custom: Boolean(t.is_custom),
  }));

  if (includeAuto) {
    return [{ label: "跟随系统默认配置 (推荐)", value: "auto" }, ...options];
  }
  return options;
}
