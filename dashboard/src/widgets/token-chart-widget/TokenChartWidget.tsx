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
    topics: "话题挖掘",
    user_titles: "群友画像",
    golden_quotes: "精彩金句",
    comic_storyboard: "今日漫画",
  };

  const pieData = Object.entries(perAnalyzer).map(([k, v]) => ({
    name: analyzerLabels[k] || k,
    value: v.total_tokens || 0,
  }));

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
      <div style={{ height: 230 }}>
        <ReactECharts option={pieOption} style={{ height: "100%", width: "100%" }} />
      </div>
    </Card>
  );
};
