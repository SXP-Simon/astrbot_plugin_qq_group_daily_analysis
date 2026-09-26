import type { components } from "../../../shared/api/generated/schema";

export type PluginLogItem = components["schemas"]["PluginLogItem"];
export type AvailableTag = components["schemas"]["AvailableTag"];
export type PluginLogResponse = components["schemas"]["PluginLogResponse"];

export const TAG_STYLE_MAP: Record<string, { label: string; color: string }> = {
  LLM: { label: "大模型调用", color: "purple" },
  Comic: { label: "群漫画", color: "magenta" },
  Album: { label: "群相册", color: "magenta" },
  OneBot: { label: "OneBot协议", color: "blue" },
  QQOfficial: { label: "QQ官方机器人", color: "cyan" },
  Telegram: { label: "Telegram平台", color: "geekblue" },
  Discord: { label: "Discord平台", color: "geekblue" },
  Scheduler: { label: "定时与调度", color: "green" },
  Resilience: { label: "容错与重试", color: "lime" },
  Render: { label: "报告与长图", color: "cyan" },
  WebUI: { label: "控制台交互", color: "processing" },
  Trace: { label: "链路追踪", color: "purple" },
};
