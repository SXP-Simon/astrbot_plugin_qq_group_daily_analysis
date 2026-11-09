import { ReportItem } from "@/entities/report/model/types";
import { DEFAULT_REPORT_TEMPLATES, ReportTemplateItem } from "@/entities/report/model/templates";

import { mockTraces } from "./traces";

/** 图片与网页报告沿用任务实际声明的文件名和归属，不再维护另一份错位清单。 */
export const mockReportHistory: ReportItem[] = [
  ...mockTraces.flatMap((trace) =>
    (trace.report_files ?? []).flatMap((file): ReportItem[] => {
      if (!file.filename || !/\.(png|jpe?g|webp|html?)$/i.test(file.filename)) return [];
      const isHtml = /\.html?$/i.test(file.filename);
      const isComic = file.report_type === "comic";
      return [
        {
          filename: file.filename,
          size_bytes: file.size_bytes ?? 0,
          modified_at: file.created_at ?? trace.completed_at ?? trace.started_at,
          group_id: trace.group_id,
          group_name: trace.group_name,
          platform: trace.platform,
          report_type: isHtml ? "html" : isComic ? "comic" : "image",
          is_html: isHtml,
          is_comic: isComic,
          trace_id: trace.trace_id,
        },
      ];
    }),
  ),
  {
    filename: "report_123456789_2026-09-25.png",
    size_bytes: 624500,
    modified_at: (Date.now() - 86400000) / 1000,
    group_id: "123456789",
    group_name: "技术交流与闲聊吹水群",
    platform: "aiocqhttp",
    report_type: "image",
  },
  {
    filename: "report_987654321_2026-09-25.png",
    size_bytes: 489200,
    modified_at: (Date.now() - 85000000) / 1000,
    group_id: "987654321",
    group_name: "AstrBot 核心测试群",
    platform: "aiocqhttp",
    report_type: "image",
  },
];

const templateExamples: ReportTemplateItem[] = [
  {
    id: "scrapbook",
    label: "Scrapbook (默认手账风)",
    display_name: "默认手账风",
    desc: "手账贴纸风格，丰富拼贴与涂鸦设计，温馨可爱，支持头像与词云展示",
    tag: "默认推荐",
    tag_color: "orange",
    is_custom: false,
    has_image: true,
    has_typst: true,
    has_html: true,
  },
  {
    id: "spring_festival",
    label: "Spring Festival (新春佳节)",
    display_name: "新春佳节",
    desc: "中国传统喜庆红金配色，新春佳节主题",
    tag: "新春年节",
    tag_color: "red",
    is_custom: false,
    has_image: true,
    has_typst: true,
    has_html: true,
  },
  {
    id: "hack",
    label: "Hack (黑客终端)",
    display_name: "黑客终端",
    desc: "赛博朋克极客终端，深黑背景与荧光绿代码风",
    tag: "黑客极客",
    tag_color: "lime",
    is_custom: false,
    has_image: true,
    has_typst: true,
    has_html: true,
  },
  {
    id: "retro_futurism",
    label: "Retro Futurism (复古未来)",
    display_name: "复古未来",
    desc: "复古未来主义与像素霓虹排版风格",
    tag: "复古像素",
    tag_color: "purple",
    is_custom: false,
    has_image: true,
    has_typst: true,
  },
  {
    id: "ATRI",
    label: "ATRI (亚托莉海洋风)",
    display_name: "亚托莉海洋风",
    desc: "《ATRI -My Dear Moments-》水下与海洋蓝调沉浸设计",
    tag: "水下海洋",
    tag_color: "blue",
    is_custom: false,
    has_image: true,
    has_typst: true,
  },
  {
    id: "custom_hacker",
    label: "极客暗黑终端 (Custom)",
    display_name: "极客暗黑终端",
    desc: "高对比度终端暗色风格海报，绿色等宽代码风格输出",
    tag: "自定义模板",
    tag_color: "purple",
    is_custom: true,
    can_uninstall: true,
    has_image: true,
    has_typst: false,
  },
  {
    id: "custom_native",
    label: "原生极简示例",
    is_custom: true,
    can_uninstall: true,
    has_image: false,
    has_html: false,
    has_typst: true,
    desc: "仅支持 Typst 图片，用于检查引擎筛选与能力标签",
  },
];

export const mockReportTemplates: ReportTemplateItem[] = [
  {
    id: "my_miku",
    label: "我的初音模板 (my_miku)",
    display_name: "我的初音模板",
    desc: "自定义的 Miku 日报，源码和角色素材放在同一个模板包内。",
    is_custom: true,
    has_typst: true,
    can_uninstall: true,
  },
  {
    id: "my_maria",
    label: "我的 Maria 模板 (my_maria)",
    display_name: "我的 Maria 模板",
    desc: "手动维护的 Maria 模板。",
    is_custom: true,
    has_typst: true,
    can_uninstall: true,
  },
  ...DEFAULT_REPORT_TEMPLATES.map((item) => ({
    ...item,
    ...templateExamples.find((example) => example.id === item.id),
  })),
  ...templateExamples.filter((item) => item.is_custom),
];
