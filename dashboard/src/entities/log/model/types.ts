export interface PluginLogItem {
  id: string;
  timestamp: number;
  time_str: string;
  level: "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL";
  logger_name: string;
  trace_id?: string | null;
  stage?: string | null;
  tag: string;
  message: string;
  raw: string;
}

export interface AvailableTag {
  key: string;
  label: string;
}

export interface PluginLogResponse {
  items: PluginLogItem[];
  total: number;
  available_tags: AvailableTag[];
}

export const TAG_STYLE_MAP: Record<string, { label: string; color: string }> = {
  LLM: { label: "大模型调用", color: "purple" },
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
