import type { components } from "@/shared/api/generated/schema";
import { z } from "zod";

export type PluginLogItem = components["schemas"]["PluginLogItem"];
export type AvailableTag = components["schemas"]["AvailableTag"];
export type PluginLogResponse = components["schemas"]["PluginLogResponse"];

export const logEntrySchema: z.ZodType<PluginLogItem> = z.object({
  id: z.string().min(1),
  timestamp: z.number(),
  time_str: z.string(),
  level: z.enum(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]),
  logger_name: z.string(),
  tag: z.string(),
  message: z.string(),
  raw: z.string(),
  trace_id: z.string().nullish(),
  stage: z.string().nullish(),
  location: z.string().nullish(),
  function_name: z.string().nullish(),
});

export const LOG_TAG_GROUPS = [
  "分析与任务",
  "报告与资源",
  "平台接入",
  "系统与数据",
  "其他",
] as const;

export const TAG_STYLE_MAP: Record<
  string,
  { label: string; color: string; group: (typeof LOG_TAG_GROUPS)[number] }
> = {
  Messages: { label: "消息采集与清洗", color: "blue", group: "分析与任务" },
  LLM: { label: "大模型调用", color: "purple", group: "分析与任务" },
  Tasks: { label: "任务执行与恢复", color: "blue", group: "分析与任务" },
  Incremental: { label: "增量分析", color: "green", group: "分析与任务" },
  Scheduler: { label: "定时与调度", color: "green", group: "分析与任务" },
  Resilience: { label: "容错与重试", color: "lime", group: "分析与任务" },
  Trace: { label: "链路追踪", color: "purple", group: "分析与任务" },
  Typst: { label: "Typst 本地排版", color: "cyan", group: "报告与资源" },
  T2I: { label: "T2I 网页转图片", color: "cyan", group: "报告与资源" },
  Render: { label: "报告与模板", color: "cyan", group: "报告与资源" },
  Resources: { label: "字体与素材", color: "geekblue", group: "报告与资源" },
  Comic: { label: "群漫画", color: "magenta", group: "报告与资源" },
  Album: { label: "群相册", color: "magenta", group: "报告与资源" },
  Dispatch: { label: "消息发送与上传", color: "blue", group: "报告与资源" },
  OneBot: { label: "OneBot 协议", color: "blue", group: "平台接入" },
  QQOfficial: { label: "QQ 官方机器人", color: "cyan", group: "平台接入" },
  Telegram: { label: "Telegram 平台", color: "geekblue", group: "平台接入" },
  Discord: { label: "Discord 平台", color: "geekblue", group: "平台接入" },
  Satori: { label: "Satori 平台", color: "geekblue", group: "平台接入" },
  Platform: { label: "平台连接与鉴权", color: "blue", group: "平台接入" },
  Config: { label: "配置与升级", color: "gold", group: "系统与数据" },
  Storage: { label: "历史与存储", color: "geekblue", group: "系统与数据" },
  WebUI: { label: "控制台交互", color: "processing", group: "系统与数据" },
  General: { label: "通用日志", color: "default", group: "系统与数据" },
};
