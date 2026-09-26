import { ReportItem } from "../../entities/report/model/types";
import { ReportTemplateItem } from "../../entities/report/model/templates";

/**
 * 历史产物报告 Mock 数据矩阵
 * 包含：日报长图 (PNG)、四格/六格群漫画 (Comic PNG)、可交互式 HTML 报告等多格式与多平台案例
 */
export const mockReportHistory: ReportItem[] = [
  // 1. 标准日报长图
  {
    filename: "daily_analysis_123456789_2026-09-26.png",
    size_bytes: 482910,
    modified_at: (Date.now() - 3600000) / 1000,
    group_id: "123456789",
    group_name: "技术交流与闲聊吹水群",
    platform: "aiocqhttp",
    report_type: "image",
    trace_id: "trace-20260926-001",
  },
  // 2. 稠密高负载群长图
  {
    filename: "daily_analysis_8899001122_2026-09-26.png",
    size_bytes: 1420500,
    modified_at: (Date.now() - 7200000) / 1000,
    group_id: "8899001122",
    group_name: "🌸 2026 深度学习与自然语言处理前沿学术讨论暨核心内测技术交流特大群 (第 3 分群) 🚀",
    platform: "aiocqhttp",
    report_type: "image",
    trace_id: "trace-20260926-002-dense",
  },
  // 3. 多模态群漫画
  {
    filename: "comic_8899001122_2026-09-26.png",
    size_bytes: 2840000,
    modified_at: (Date.now() - 7167500) / 1000,
    group_id: "8899001122",
    group_name: "🌸 2026 深度学习与自然语言处理前沿学术讨论暨核心内测技术交流特大群 (第 3 分群) 🚀",
    platform: "aiocqhttp",
    report_type: "comic",
    trace_id: "trace-20260926-002-dense",
  },
  // 4. 独立可交互 HTML 报告
  {
    filename: "interactive_report_8899001122_2026-09-26.html",
    size_bytes: 385000,
    modified_at: (Date.now() - 7166000) / 1000,
    group_id: "8899001122",
    group_name: "🌸 2026 深度学习与自然语言处理前沿学术讨论暨核心内测技术交流特大群 (第 3 分群) 🚀",
    platform: "aiocqhttp",
    report_type: "html",
    is_html: true,
    trace_id: "trace-20260926-002-dense",
  },
  // 5. Telegram 渠道告警日报
  {
    filename: "daily_analysis_telegram_1001987654321.png",
    size_bytes: 420000,
    modified_at: (Date.now() - 900000) / 1000,
    group_id: "-1001987654321",
    group_name: "DevOps & SRE Infra Alert Channel [PROD]",
    platform: "telegram",
    report_type: "image",
    trace_id: "trace-20260926-005-tg-warning",
  },
  // 6. Discord 社区复古像素日报
  {
    filename: "daily_analysis_discord_1082739182374.png",
    size_bytes: 610000,
    modified_at: (Date.now() - 86400000) / 1000,
    group_id: "1082739182374",
    group_name: "🎮 Indie Game Dev & Pixel Art Guild",
    platform: "discord",
    report_type: "image",
    trace_id: "trace-20260925-006-discord",
  },
  // 7. 昨日历史日报
  {
    filename: "report_123456789_2026-09-25.png",
    size_bytes: 624500,
    modified_at: (Date.now() - 86400000) / 1000,
    group_id: "123456789",
    group_name: "技术交流与闲聊吹水群",
    platform: "aiocqhttp",
    report_type: "image",
  },
  // 8. 核心测试群历史日报
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

export const mockReportTemplates: ReportTemplateItem[] = [
  {
    id: "scrapbook",
    label: "Scrapbook (默认手账风)",
    display_name: "默认手账风",
    desc: "手账贴纸风格，丰富拼贴与涂鸦设计，温馨可爱，支持头像与词云展示",
    tag: "默认推荐",
    tag_color: "orange",
    is_custom: false,
    has_image: true,
    has_html: true,
  },
  {
    id: "spring_card",
    label: "Spring Card (清新春意卡片)",
    display_name: "清新春意卡片",
    desc: "简洁高质感卡片布局，柔和渐变色调与扁平化话题分区",
    tag: "现代简约",
    tag_color: "green",
    is_custom: false,
    has_image: true,
    has_html: true,
  },
  {
    id: "cyberpunk_neon",
    label: "Cyberpunk Neon (赛博朋克霓虹)",
    display_name: "赛博朋克霓虹",
    desc: "黑紫暗调霓虹发光质感，专为夜间高频技术群与极客群设计",
    tag: "赛博极客",
    tag_color: "magenta",
    is_custom: false,
    has_image: true,
    has_html: true,
  },
  {
    id: "pixel_game",
    label: "Pixel Game (复古像素游戏)",
    display_name: "复古像素游戏",
    desc: "8-bit 复古像素边框与点阵字体，游戏交流群与二次元群首选",
    tag: "复古怀旧",
    tag_color: "cyan",
    is_custom: false,
    has_image: true,
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
  },
];
