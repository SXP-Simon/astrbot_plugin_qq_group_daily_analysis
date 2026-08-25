import React from "react";
import { Card, Empty } from "antd";
import ReactECharts from "echarts-for-react";
import { PieChartOutlined } from "@ant-design/icons";
import { TokenUsage } from "../../entities/trace/model/types";

interface TokenChartWidgetProps {
  tokenUsage: TokenUsage;
}

export const TokenChartWidget: React.FC<TokenChartWidgetProps> = ({ tokenUsage }) => {
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
    }));

  const hasTokens = (tokenUsage.total_tokens || 0) > 0 || pieData.length > 0;

  const pieOption = {
    tooltip: {
      trigger: "item",
      formatter: "{b}: {c} ({d}%)",
    },
    legend: {
      bottom: "0%",
      left: "center",
      textStyle: { fontSize: 11 },
    },
    series: [
      {
        name: "模型消耗",
        type: "pie",
        radius: ["40%", "70%"],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: "#fff",
          borderWidth: 2,
        },
        label: { show: false },
        data: pieData.length > 0 ? pieData : [{ name: "全流程分析", value: tokenUsage.total_tokens }],
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
