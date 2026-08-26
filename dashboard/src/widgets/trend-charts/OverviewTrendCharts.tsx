import React, { useState, useEffect } from "react";
import { Row, Col, Card, Empty, Typography, Space, Radio } from "antd";
import ReactECharts from "echarts-for-react";
import {
  AreaChartOutlined,
  BarChartOutlined,
  PieChartOutlined,
} from "@ant-design/icons";
import {
  AnalyticsTrendsResponse,
  AnalyticsTrendPoint,
  ProviderBreakdownItem,
} from "../../entities/metric/model/types";
import { fetchAnalyticsTrends } from "../../entities/metric/api/metricApi";
import { formatTokens, formatSmartTokens } from "../../shared/lib/formatters";
import { useTheme } from "../../shared/lib/useTheme";

const { Text } = Typography;

interface OverviewTrendChartsProps {
  initialTrends?: AnalyticsTrendsResponse;
  totalTraces: number;
  totalTokens: number;
  loading?: boolean;
}

type RangeOption = "48h" | "7d" | "14d" | "30d";

export const OverviewTrendCharts: React.FC<OverviewTrendChartsProps> = ({
  initialTrends,
  totalTraces,
  totalTokens,
  loading: parentLoading = false,
}) => {
  const { isDark } = useTheme();
  const [selectedRange, setSelectedRange] = useState<RangeOption>("14d");
  const [trendData, setTrendData] = useState<AnalyticsTrendsResponse | undefined>(initialTrends);
  const [fetching, setFetching] = useState(false);

  useEffect(() => {
    if (initialTrends && selectedRange === "14d") {
      setTrendData(initialTrends);
    }
  }, [initialTrends, selectedRange]);

  const handleRangeChange = async (val: RangeOption) => {
    setSelectedRange(val);
    let granularity: "day" | "hour" = "day";
    let rangeCount = 14;

    if (val === "48h") {
      granularity = "hour";
      rangeCount = 48;
    } else if (val === "7d") {
      granularity = "day";
      rangeCount = 7;
    } else if (val === "14d") {
      granularity = "day";
      rangeCount = 14;
    } else if (val === "30d") {
      granularity = "day";
      rangeCount = 30;
    }

    setFetching(true);
    try {
      const res = await fetchAnalyticsTrends(granularity, rangeCount);
      if (res) {
        setTrendData(res);
      }
    } finally {
      setFetching(false);
    }
  };

  const points: AnalyticsTrendPoint[] = trendData?.points || [];
  const providers: ProviderBreakdownItem[] = (trendData?.provider_breakdown || []).filter(
    (p) => p.total_tokens > 0 || p.request_count > 0
  );

  const hasData = points.length > 0;
  const dates = points.map((t) => t.date);
  const requestCounts = points.map((t) => t.request_count);
  const promptTokens = points.map((t) => t.prompt_tokens);
  const completionTokens = points.map((t) => t.completion_tokens);

  // 计算当前视图区间的总请求与总 Token
  const rangeTotalRequests = points.reduce((acc, p) => acc + (p.request_count || 0), 0);
  const rangeTotalTokens = points.reduce((acc, p) => acc + (p.total_tokens || 0), 0);

  // 1. API 请求次数面积图 Option
  const requestChartOption = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      backgroundColor: isDark ? "rgba(22, 27, 34, 0.96)" : "rgba(255, 255, 255, 0.98)",
      borderColor: isDark ? "#30363d" : "#e2e8f0",
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: isDark ? "#c9d1d9" : "#1e293b", fontSize: 12 },
      formatter: (params: Array<{ dataIndex: number }>) => {
        if (!params || params.length === 0) return "";
        const idx = params[0].dataIndex;
        const item = points[idx];
        if (!item) return "";
        return `
          <div style="font-weight: 600; font-family: monospace; font-size: 12px; margin-bottom: 6px; color: ${isDark ? "#ffffff" : "#0f172a"};">
            ${item.date_full || item.date}
          </div>
          <div style="font-size: 12px; color: #2563eb; margin-bottom: 3px;">
            分析触发次数: <b>${item.request_count}</b> 次
          </div>
          <div style="font-size: 11px; color: #16a34a;">
            成功: ${item.succeeded_count} 次 / 失败: <span style="color: ${item.failed_count > 0 ? "#dc2626" : "#64748b"}">${item.failed_count} 次</span>
          </div>
        `;
      },
    },
    grid: {
      top: 15,
      right: 15,
      bottom: 25,
      left: 35,
      containLabel: false,
    },
    xAxis: {
      type: "category",
      data: dates,
      axisLine: { lineStyle: { color: isDark ? "#30363d" : "#e2e8f0" } },
      axisTick: { show: false },
      axisLabel: {
        color: isDark ? "#8b949e" : "#64748b",
        fontSize: 11,
        fontFamily: "monospace",
      },
    },
    yAxis: {
      type: "value",
      splitLine: {
        lineStyle: {
          color: isDark ? "#21262d" : "#f1f5f9",
          type: "dashed",
        },
      },
      axisLabel: {
        color: isDark ? "#8b949e" : "#64748b",
        fontSize: 11,
        fontFamily: "monospace",
      },
    },
    series: [
      {
        name: "请求次数",
        type: "line",
        smooth: true,
        showSymbol: false,
        symbolSize: 6,
        data: requestCounts,
        lineStyle: {
          width: 2,
          color: "#2563eb",
        },
        itemStyle: {
          color: "#2563eb",
        },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(37, 99, 235, 0.45)" },
              { offset: 0.8, color: "rgba(37, 99, 235, 0.08)" },
              { offset: 1, color: "rgba(37, 99, 235, 0.0)" },
            ],
          },
        },
      },
    ],
  };

  // 2. Tokens 消耗堆叠柱状图 Option
  const tokenChartOption = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "axis",
      backgroundColor: isDark ? "rgba(22, 27, 34, 0.96)" : "rgba(255, 255, 255, 0.98)",
      borderColor: isDark ? "#30363d" : "#e2e8f0",
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: isDark ? "#c9d1d9" : "#1e293b", fontSize: 12 },
      formatter: (params: Array<{ dataIndex: number }>) => {
        if (!params || params.length === 0) return "";
        const idx = params[0].dataIndex;
        const item = points[idx];
        if (!item) return "";
        return `
          <div style="font-weight: 600; font-family: monospace; font-size: 12px; margin-bottom: 6px; color: ${isDark ? "#ffffff" : "#0f172a"};">
            ${item.date_full || item.date}
          </div>
          <div style="font-size: 12px; color: #2563eb; margin-bottom: 3px;">
            总消耗: <b style="font-family: monospace;">${formatTokens(item.total_tokens)}</b>
          </div>
          <div style="font-size: 11px; color: ${isDark ? "#8b949e" : "#64748b"}; font-family: monospace;">
            输入 (Prompt): ${formatTokens(item.prompt_tokens)}
          </div>
          <div style="font-size: 11px; color: ${isDark ? "#8b949e" : "#64748b"}; font-family: monospace;">
            输出 (Completion): ${formatTokens(item.completion_tokens)}
          </div>
        `;
      },
    },
    grid: {
      top: 15,
      right: 15,
      bottom: 25,
      left: 45,
      containLabel: false,
    },
    xAxis: {
      type: "category",
      data: dates,
      axisLine: { lineStyle: { color: isDark ? "#30363d" : "#e2e8f0" } },
      axisTick: { show: false },
      axisLabel: {
        color: isDark ? "#8b949e" : "#64748b",
        fontSize: 11,
        fontFamily: "monospace",
      },
    },
    yAxis: {
      type: "value",
      splitLine: {
        lineStyle: {
          color: isDark ? "#21262d" : "#f1f5f9",
          type: "dashed",
        },
      },
      axisLabel: {
        color: isDark ? "#8b949e" : "#64748b",
        fontSize: 11,
        fontFamily: "monospace",
        formatter: (val: number) => (val >= 1000 ? `${Math.round(val / 1000)}k` : `${val}`),
      },
    },
    series: [
      {
        name: "输入 Tokens (Prompt)",
        type: "bar",
        stack: "tokens",
        data: promptTokens,
        itemStyle: {
          color: "#2563eb",
          borderRadius: [0, 0, 0, 0],
        },
      },
      {
        name: "输出 Tokens (Completion)",
        type: "bar",
        stack: "tokens",
        data: completionTokens,
        itemStyle: {
          color: "#60a5fa",
          borderRadius: [3, 3, 0, 0],
        },
      },
    ],
  };

  // 3. 服务商消耗占比环形饼图 (Donut Chart Option)
  // 专业沉稳的调色板（支持动态扩展与循环）
  const DONUT_PALETTE = [
    "#2563eb", // 主蓝
    "#0284c7", // 浅蓝
    "#0d9488", // 青绿
    "#16a34a", // 翠绿
    "#7c3aed", // 紫罗兰
    "#9333ea", // 紫色
    "#ea580c", // 暖橙
    "#0891b2", // 湖蓝
    "#475569", // 蓝灰
    "#94a3b8", // 浅灰（其他）
  ];

  // 超过 7 个服务商时进行 Top 6 聚合，其余归入“其他服务商”，保证环形图始终清晰易读
  const sortedProviders = [...providers].sort(
    (a, b) => (b.total_tokens || 0) - (a.total_tokens || 0)
  );

  let pieDataList: { name: string; value: number }[] = [];
  if (sortedProviders.length <= 7) {
    pieDataList = sortedProviders.map((p) => ({
      name: p.name,
      value: p.total_tokens,
    }));
  } else {
    const top6 = sortedProviders.slice(0, 6);
    const others = sortedProviders.slice(6);
    const otherTokens = others.reduce((acc, p) => acc + (p.total_tokens || 0), 0);
    pieDataList = [
      ...top6.map((p) => ({ name: p.name, value: p.total_tokens })),
      { name: `其他服务商 (${others.length}个)`, value: otherTokens },
    ];
  }

  const pieChartOption = {
    backgroundColor: "transparent",
    tooltip: {
      trigger: "item",
      backgroundColor: isDark ? "rgba(22, 27, 34, 0.96)" : "rgba(255, 255, 255, 0.98)",
      borderColor: isDark ? "#30363d" : "#e2e8f0",
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: isDark ? "#c9d1d9" : "#1e293b", fontSize: 12 },
      formatter: (params: { name: string; value: number; percent: number }) => {
        return `
          <div style="font-weight: 600; font-family: monospace; font-size: 12px; margin-bottom: 4px; color: ${isDark ? "#ffffff" : "#0f172a"};">
            ${params.name}
          </div>
          <div style="font-size: 11px; color: #2563eb;">
            消耗: <b>${formatSmartTokens(params.value)}</b> Tokens (${params.percent}%)
          </div>
        `;
      },
    },
    legend: {
      orient: "vertical",
      right: 4,
      top: "center",
      itemWidth: 8,
      itemHeight: 8,
      textStyle: {
        color: isDark ? "#8b949e" : "#64748b",
        fontSize: 11,
        fontFamily: "monospace",
      },
      formatter: (name: string) => {
        const shortName = name.length > 14 ? `${name.slice(0, 12)}...` : name;
        return shortName;
      },
    },
    series: [
      {
        name: "消耗分布",
        type: "pie",
        radius: ["48%", "72%"],
        center: ["36%", "50%"],
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 3,
          borderColor: isDark ? "#161b22" : "#ffffff",
          borderWidth: 2,
        },
        label: {
          show: false,
        },
        data: pieDataList.map((item, idx) => ({
          name: item.name,
          value: item.value,
          itemStyle: { color: DONUT_PALETTE[idx % DONUT_PALETTE.length] },
        })),
      },
    ],
  };

  const currentLoading = parentLoading || fetching;

  return (
    <Card
      size="small"
      style={{
        background: isDark ? "#161b22" : "#ffffff",
        borderColor: isDark ? "#30363d" : "#e2e8f0",
      }}
      styles={{ body: { padding: "14px 16px" } }}
    >
      {/* 顶部标题与时间跨度切换器 */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 12,
          flexWrap: "wrap",
          gap: 8,
        }}
      >
        <Space size={6} align="center">
          <AreaChartOutlined style={{ color: "#2563eb", fontSize: 13 }} />
          <Text strong style={{ fontSize: 13, letterSpacing: "-0.2px", color: isDark ? "#c9d1d9" : "#1e293b" }}>
            分析行为与 Token 消耗可观测趋势
          </Text>
        </Space>

        <Radio.Group
          size="small"
          value={selectedRange}
          onChange={(e) => handleRangeChange(e.target.value)}
          buttonStyle="solid"
        >
          <Radio.Button value="48h" style={{ fontSize: 12 }}>近48小时</Radio.Button>
          <Radio.Button value="7d" style={{ fontSize: 12 }}>近7天</Radio.Button>
          <Radio.Button value="14d" style={{ fontSize: 12 }}>近14天</Radio.Button>
          <Radio.Button value="30d" style={{ fontSize: 12 }}>近30天</Radio.Button>
        </Radio.Group>
      </div>

      {/* 趋势图表三大矩阵：请求次数面积图 + Token 柱状图 + 服务商占比环形图 */}
      <Row gutter={[16, 16]}>
        {/* 1. API 请求次数趋势图 */}
        <Col xs={24} lg={8}>
          <div
            style={{
              padding: "10px 12px",
              background: isDark ? "#0d1117" : "#f8fafc",
              border: `1px solid ${isDark ? "#21262d" : "#e2e8f0"}`,
              borderRadius: 6,
              height: "100%",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <Text strong style={{ fontSize: 12, color: isDark ? "#c9d1d9" : "#334155" }}>
                <AreaChartOutlined style={{ color: "#2563eb", marginRight: 6 }} />
                API 请求次数
              </Text>
              <Text strong className="font-mono" style={{ fontSize: 12, color: "#2563eb" }}>
                {rangeTotalRequests > 0 ? `${rangeTotalRequests} 次` : `${totalTraces} 次`}
              </Text>
            </div>

            {hasData ? (
              <ReactECharts
                option={requestChartOption}
                style={{ height: 160, width: "100%" }}
                opts={{ renderer: "svg" }}
                showLoading={currentLoading}
              />
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无请求趋势数据"
                style={{ height: 160, display: "flex", flexDirection: "column", justifyContent: "center" }}
              />
            )}
          </div>
        </Col>

        {/* 2. Tokens 消耗趋势图 */}
        <Col xs={24} lg={8}>
          <div
            style={{
              padding: "10px 12px",
              background: isDark ? "#0d1117" : "#f8fafc",
              border: `1px solid ${isDark ? "#21262d" : "#e2e8f0"}`,
              borderRadius: 6,
              height: "100%",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <Text strong style={{ fontSize: 12, color: isDark ? "#c9d1d9" : "#334155" }}>
                <BarChartOutlined style={{ color: "#2563eb", marginRight: 6 }} />
                Tokens 消耗趋势
              </Text>
              <Text strong className="font-mono" style={{ fontSize: 12, color: "#2563eb" }}>
                {rangeTotalTokens > 0 ? formatSmartTokens(rangeTotalTokens) : formatSmartTokens(totalTokens)}
              </Text>
            </div>

            {hasData ? (
              <ReactECharts
                option={tokenChartOption}
                style={{ height: 160, width: "100%" }}
                opts={{ renderer: "svg" }}
                showLoading={currentLoading}
              />
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无 Token 消耗趋势数据"
                style={{ height: 160, display: "flex", flexDirection: "column", justifyContent: "center" }}
              />
            )}
          </div>
        </Col>

        {/* 3. 服务商消耗占比环形图 */}
        <Col xs={24} lg={8}>
          <div
            style={{
              padding: "10px 12px",
              background: isDark ? "#0d1117" : "#f8fafc",
              border: `1px solid ${isDark ? "#21262d" : "#e2e8f0"}`,
              borderRadius: 6,
              height: "100%",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <Text strong style={{ fontSize: 12, color: isDark ? "#c9d1d9" : "#334155" }}>
                <PieChartOutlined style={{ color: "#2563eb", marginRight: 6 }} />
                服务商消耗占比
              </Text>
              <Text strong className="font-mono" style={{ fontSize: 12, color: "#64748b" }}>
                {providers.length} 个渠道
              </Text>
            </div>

            {providers.length > 0 ? (
              <ReactECharts
                option={pieChartOption}
                style={{ height: 160, width: "100%" }}
                opts={{ renderer: "svg" }}
                showLoading={currentLoading}
              />
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无服务商消耗分布"
                style={{ height: 160, display: "flex", flexDirection: "column", justifyContent: "center" }}
              />
            )}
          </div>
        </Col>
      </Row>
    </Card>
  );
};
