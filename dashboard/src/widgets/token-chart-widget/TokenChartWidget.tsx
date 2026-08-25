import React from "react";
import { Card } from "antd";
import ReactECharts from "echarts-for-react";
import { PieChartOutlined } from "@ant-design/icons";
import { TokenUsage } from "../../entities/trace/model/types";

interface TokenChartWidgetProps {
  tokenUsage: TokenUsage;
}

export const TokenChartWidget: React.FC<TokenChartWidgetProps> = ({ tokenUsage }) => {
  const perAnalyzer = tokenUsage.per_analyzer || {};

  const analyzerLabels: Record<string, string> = {
    topics: "话题挖掘 (Topics)",
    user_titles: "人物画像 (Titles)",
    golden_quotes: "金句提取 (Quotes)",
    comic_storyboard: "漫画分镜 (Comics)",
  };

  const pieData = Object.entries(perAnalyzer).map(([k, v]) => ({
    name: analyzerLabels[k] || k,
    value: v.total_tokens || 0,
  }));

  const pieOption = {
    tooltip: {
      trigger: "item",
      formatter: "{b}: {c} Tokens ({d}%)",
    },
    legend: {
      bottom: "0%",
      left: "center",
      textStyle: { fontSize: 11 },
    },
    series: [
      {
        name: "Token 消耗",
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
          子分析器 Token 消耗占比 (Token Breakdown)
        </span>
      }
    >
      <div style={{ height: 230 }}>
        <ReactECharts option={pieOption} style={{ height: "100%", width: "100%" }} />
      </div>
    </Card>
  );
};
