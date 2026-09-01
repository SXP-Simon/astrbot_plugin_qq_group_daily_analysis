/**
 * 依据各阶段特性（本地计算 vs 外部协议 vs 大模型 vs 绘图）制定 SLA 健康基线与超时预算
 */
export function getStageSlaThreshold(stageName: string): {
  thresholdMs: number;
  description: string;
} {
  const norm = (stageName || "").toUpperCase();
  if (
    norm.includes("LLM") ||
    norm.includes("话题") ||
    norm.includes("画像") ||
    norm.includes("金句")
  ) {
    return { thresholdMs: 120000, description: "大模型多轮分析健康阈值 120s" };
  }
  if (
    norm.includes("COMIC") ||
    norm.includes("漫画") ||
    norm.includes("DRAW") ||
    norm.includes("T2I")
  ) {
    return { thresholdMs: 180000, description: "文生图/绘图排队健康阈值 180s" };
  }
  if (
    norm.includes("RENDER") ||
    norm.includes("渲染") ||
    norm.includes("REPORT")
  ) {
    return { thresholdMs: 45000, description: "长图渲染与平台发送健康阈值 45s" };
  }
  if (norm.includes("FETCH") || norm.includes("拉取")) {
    return { thresholdMs: 20000, description: "平台消息抓取健康阈值 20s" };
  }
  if (
    norm.includes("CLEAN") ||
    norm.includes("清洗") ||
    norm.includes("STATS") ||
    norm.includes("统计") ||
    norm.includes("SAVE") ||
    norm.includes("持久化")
  ) {
    return { thresholdMs: 5000, description: "本地计算/SQLite 处理健康阈值 5s" };
  }
  return { thresholdMs: 30000, description: "常规流程健康阈值 30s" };
}
