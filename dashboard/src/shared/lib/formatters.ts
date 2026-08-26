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

/**
 * 智能 Token 格式化：
 * - 小于 100万 时完整显示千分位数值（如 16,292）
 * - 达到或超过 100万 时紧凑显示 M（如 1.25M）
 * - 达到或超过 10亿 时紧凑显示 B（如 2.50B）
 */
export function formatSmartTokens(tokens?: number): string {
  if (tokens === undefined || tokens === null) return "-";
  if (tokens >= 1_000_000_000) {
    return `${(tokens / 1_000_000_000).toFixed(2)}B`;
  }
  if (tokens >= 1_000_000) {
    return `${(tokens / 1_000_000).toFixed(2)}M`;
  }
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
    COMIC_STORYBOARD: "漫画分镜提示词提取",
    COMIC_DRAWING: "漫画长图生成与投递",
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
    case "comic":
    case "comic_manual":
      return { text: "群漫画生成", color: "magenta" };
    case "web_ui":
    case "web_manual":
      return { text: "控制台触发", color: "geekblue" };
    case "resume":
    case "resume_analysis":
      return { text: "断点续跑", color: "orange" };
    case "rerender":
    case "rerender_report":
      return { text: "主题重绘", color: "volcano" };
    default:
      return { text: triggerType || "常规分析", color: "default" };
  }
}


