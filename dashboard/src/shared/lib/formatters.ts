/**
 * 格式化与数据转换工具函数库 (Shared Formatters)
 */

export function formatDuration(durationMs?: number): string {
  if (!durationMs || durationMs <= 0) return "-";
  if (durationMs < 1000) return `${Math.round(durationMs)}ms`;
  return `${(durationMs / 1000).toFixed(2)}s`;
}

export function formatTokens(tokens?: number): string {
  if (tokens === undefined || tokens === null) return "-";
  return tokens.toLocaleString();
}

export function formatCost(costUsd?: number): string {
  if (costUsd === undefined || costUsd === null) return "$0.00";
  return `$${costUsd.toFixed(4)}`;
}

export function formatTimestamp(ts?: number): string {
  if (!ts) return "-";
  const d = new Date(ts * 1000);
  return `${d.toLocaleDateString()} ${d.toLocaleTimeString()}`;
}

export function formatRelativeTime(secondsAgo: number): string {
  if (secondsAgo < 60) return `${Math.round(secondsAgo)}秒前`;
  if (secondsAgo < 3600) return `${Math.floor(secondsAgo / 60)}分钟前`;
  return `${Math.floor(secondsAgo / 3600)}小时前`;
}

export function formatPercent(ratio?: number): string {
  if (ratio === undefined || ratio === null) return "-";
  return `${Math.round(ratio * 100)}%`;
}

export function formatStageName(stage?: string): string {
  if (!stage) return "未指定阶段";
  const stageMap: Record<string, string> = {
    FETCH_MESSAGES: "拉取聊天记录",
    CLEAN_MESSAGES: "消息清洗过滤",
    STATS_ANALYSIS: "基础统计分析",
    LLM_ANALYSIS: "大模型话题与画像分析",
    SAVE_SUMMARY: "历史记录持久化",
    RENDER_REPORT: "报告图片渲染与发送",
    CRASH_RECOVERY: "异常终止恢复",
  };
  return stageMap[stage] || stage;
}

export function formatTriggerType(triggerType?: string): { text: string; color: string } {
  switch (triggerType) {
    case "manual":
      return { text: "手动触发", color: "blue" };
    case "auto":
    case "scheduled":
      return { text: "定时分析", color: "green" };
    case "incremental":
      return { text: "增量分析", color: "purple" };
    case "auto_report":
    case "incremental_report":
      return { text: "增量日报", color: "cyan" };
    case "web_ui":
    case "web_manual":
      return { text: "控制台触发", color: "geekblue" };
    default:
      return { text: triggerType || "常规分析", color: "default" };
  }
}


