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
