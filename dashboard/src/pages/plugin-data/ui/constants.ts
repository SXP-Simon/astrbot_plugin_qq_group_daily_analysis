import React from "react";
import { message } from "antd";
import { formatStageName } from "../../../shared/lib/formatters";

// 统一现代无衬线等宽/数字字体规范，杜绝宋体/Courier等衬线体
export const SANS_NUM_STYLE: React.CSSProperties = {
  fontFamily:
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif",
  fontVariantNumeric: "tabular-nums",
  fontWeight: 600,
  fontSize: 13,
};

export interface PartitionItem {
  key: string;
  name: string;
  icon: React.ReactNode;
  pathTag: string;
  count: number;
  sizeBytes: number;
  description: string;
  impactNotice: string;
  onClear: () => void;
  clearKey: string;
}

export const getStageMeta = (stage: string): { label: string; color: string } => {
  const label = formatStageName(stage);
  const colorMap: Record<string, string> = {
    FETCH_MESSAGES: "blue",
    CLEAN_MESSAGES: "geekblue",
    STATS_ANALYSIS: "orange",
    LLM_ANALYSIS: "purple",
    SAVE_SUMMARY: "gold",
    RENDER_REPORT: "cyan",
    DISPATCH_REPORT: "green",
    COMIC_STORYBOARD: "magenta",
    COMIC_DRAWING: "volcano",
    CRASH_RECOVERY: "red",
  };
  return {
    label,
    color: colorMap[stage] || colorMap[stage.toUpperCase()] || "default",
  };
};

export const handleCopyJson = (data: unknown): void => {
  try {
    const jsonStr = JSON.stringify(data, null, 2);
    navigator.clipboard.writeText(jsonStr);
    message.success("已复制 JSON 到剪贴板");
  } catch {
    message.error("复制失败");
  }
};
