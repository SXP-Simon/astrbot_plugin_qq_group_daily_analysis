import React from "react";
import { Card, Empty } from "antd";
import ReactECharts from "echarts-for-react";
import { PieChartOutlined } from "@ant-design/icons";
import { TokenUsage } from "../../entities/trace/model/types";
import { formatTokens } from "../../shared/lib/formatters";
import { useTheme } from "../../shared/lib/useTheme";

interface TokenChartWidgetProps {
  tokenUsage: TokenUsage;
}

export const TokenChartWidget: React.FC<TokenChartWidgetProps> = ({ tokenUsage }) => {
  const { isDark } = useTheme();
  const perAnalyzer = tokenUsage.per_analyzer || {};

  const analyzerLabels: Record<string, string> = {
    topics: "话题分析",
    user_titles: "群友画像",
    golden_quotes: "精彩金句",
    chat_quality: "群聊质量",
    comic_storyboard: "趣味漫画",
  };

  const pieData = Object.entries(perAnalyzer)
    .filter(([, v]) => (v.total_tokens || 0) > 0)
    .map(([k, v]) => ({
      name: analyzerLabels[k] || k,
      value: v.total_tokens || 0,
      promptTokens: v.prompt_tokens || 0,
      completionTokens: v.completion_tokens || 0,
    }));

  const hasTokens = (tokenUsage.total_tokens || 0) > 0 || pieData.length > 0;

  const pieOption = {
    tooltip: {
      trigger: "item",
      backgroundColor: isDark ? "rgba(24, 24, 28, 0.96)" : "rgba(255, 255, 255, 0.96)",
      borderColor: isDark ? "#383838" : "#f0f0f0",
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: isDark ? "#e6edf3" : "#262626", fontSize: 12 },
      formatter: (params: {
        name: string;
        value: number;
        percent: number;
        color: string;
        data: { promptTokens?: number; completionTokens?: number };
      }) => {
        const { name, value, percent, data, color } = params;
        const prompt =
          data?.promptTokens !== undefined
            ? formatTokens(data.promptTokens)
            : "-";
        const completion =
          data?.completionTokens !== undefined
            ? formatTokens(data.completionTokens)
            : "-";
        const total = formatTokens(value);
        return `
          <div style="display: flex; align-items: center; gap: 6px; margin-bottom: 4px;">
            <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: ${color};"></span>
            <span style="font-weight: 600; font-size: 13px; color: ${isDark ? "#ffffff" : "#262626"};">${name}</span>
          </div>
          <div style="color: ${isDark ? "#bfbfbf" : "#595959"}; font-size: 12px; margin-bottom: 4px;">
            总消耗: <span style="font-weight: 600; color: #9254de;">${total}</span> (${percent}%)
          </div>
          <div style="color: ${isDark ? "#8c8c8c" : "#8c8c8c"}; font-size: 11px; padding-top: 4px; border-top: 1px dashed ${isDark ? "#383838" : "#f0f0f0"};">
            输入: <span style="color: ${isDark ? "#d9d9d9" : "#595959"};">${prompt}</span> / 输出: <span style="color: ${isDark ? "#d9d9d9" : "#595959"};">${completion}</span>
          </div>
        `;
      },
    },
    legend: {
      bottom: "0%",
      left: "center",
      textStyle: { fontSize: 11, color: isDark ? "#e6edf3" : "#595959" },
    },
    series: [
      {
        name: "模型消耗",
        type: "pie",
        radius: ["40%", "70%"],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: isDark ? "#141414" : "#fff",
          borderWidth: 2,
        },
        label: { show: false },
        data:
          pieData.length > 0
            ? pieData
            : [
                {
                  name: "全流程分析",
                  value: tokenUsage.total_tokens,
                  promptTokens: tokenUsage.prompt_tokens,
                  completionTokens: tokenUsage.completion_tokens,
                },
              ],
      },
    ],
  };

  return (
    <Card
      size="small"
      title={
        <span style={{ fontSize: 13 }}>
          <PieChartOutlined style={{ color: "#722ed1", marginRight: 6 }} />
          各模块模型消耗分布
        </span>
      }
    >
      <div style={{ height: 230, display: "flex", alignItems: "center", justifyContent: "center" }}>
        {hasTokens ? (
          <ReactECharts option={pieOption} style={{ height: "100%", width: "100%" }} />
        ) : (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="本次分析未产生模型消耗（纯统计模式或未启用大模型）"
            style={{ margin: 0 }}
          />
        )}
      </div>
    </Card>
  );
};
