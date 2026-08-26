import React, { useState, useEffect } from "react";
import { Row, Col, Card, Empty, Typography, Space, Radio, Tooltip } from "antd";
import ReactECharts from "echarts-for-react";
import {
  AreaChartOutlined,
  BarChartOutlined,
  ApartmentOutlined,
  AppstoreOutlined,
} from "@ant-design/icons";
import {
  AnalyticsTrendsResponse,
  AnalyticsTrendPoint,
  ProviderBreakdownItem,
  ModelBreakdownItem,
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
  const providers: ProviderBreakdownItem[] = trendData?.provider_breakdown || [];
  const models: ModelBreakdownItem[] = trendData?.model_breakdown || [];

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
      formatter: (params: Array<{ dataIndex: number; value: number }>) => {
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
      minInterval: 1,
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
          <div style="font-size: 12px; color: #7c3aed; margin-bottom: 3px;">
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
        name: "输入 Tokens",
        type: "bar",
        stack: "tokens",
        barMaxWidth: 16,
        itemStyle: {
          color: "#7c3aed",
        },
        data: promptTokens,
      },
      {
        name: "输出 Tokens",
        type: "bar",
        stack: "tokens",
        barMaxWidth: 16,
        itemStyle: {
          color: "#a78bfa",
          borderRadius: [2, 2, 0, 0],
        },
        data: completionTokens,
      },
    ],
  };

  const currentLoading = parentLoading || fetching;

  return (
    <Card
      size="small"
      title={
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
          <Space size={6}>
            <AreaChartOutlined style={{ color: "#2563eb" }} />
            <Text strong style={{ fontSize: 13, letterSpacing: "-0.2px" }}>
              分析行为与 Token 消耗可观测趋势
            </Text>
          </Space>

          {/* 紧凑型时间跨度切换控制器 (符合 Data-Dense 设计规范) */}
          <Radio.Group
            size="small"
            value={selectedRange}
            onChange={(e) => handleRangeChange(e.target.value as RangeOption)}
            buttonStyle="solid"
          >
            <Radio.Button value="48h" style={{ fontSize: 12 }}>近48小时</Radio.Button>
            <Radio.Button value="7d" style={{ fontSize: 12 }}>近7天</Radio.Button>
            <Radio.Button value="14d" style={{ fontSize: 12 }}>近14天</Radio.Button>
            <Radio.Button value="30d" style={{ fontSize: 12 }}>近30天</Radio.Button>
          </Radio.Group>
        </div>
      }
    >
      <Row gutter={[12, 12]}>
        {/* API 请求次数面积图 */}
        <Col xs={24} md={12}>
          <div
            style={{
              padding: "8px 12px",
              background: isDark ? "#161b22" : "#f8fafc",
              borderRadius: 4,
              border: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <Text strong style={{ fontSize: 12, color: isDark ? "#c9d1d9" : "#334155" }}>
                <AreaChartOutlined style={{ color: "#2563eb", marginRight: 6 }} />
                API 请求次数
              </Text>
              <Text strong className="font-mono" style={{ fontSize: 13, color: "#2563eb" }}>
                {rangeTotalRequests > 0 ? rangeTotalRequests.toLocaleString() : totalTraces.toLocaleString()} 次
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

        {/* Tokens 消耗柱状图 */}
        <Col xs={24} md={12}>
          <div
            style={{
              padding: "8px 12px",
              background: isDark ? "#161b22" : "#f8fafc",
              borderRadius: 4,
              border: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <Text strong style={{ fontSize: 12, color: isDark ? "#c9d1d9" : "#334155" }}>
                <BarChartOutlined style={{ color: "#7c3aed", marginRight: 6 }} />
                Tokens 消耗趋势
              </Text>
              <Text strong className="font-mono" style={{ fontSize: 13, color: "#7c3aed" }}>
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
      </Row>

      {/* 服务商 (Provider) 与模型 (Model ID) 细粒度审计统计条 (Data Dense 紧凑设计) */}
      {(providers.length > 0 || models.length > 0) && (
        <div
          style={{
            marginTop: 10,
            paddingTop: 8,
            borderTop: `1px solid ${isDark ? "#21262d" : "#f1f5f9"}`,
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 10,
          }}
        >
          {/* 服务商分布 */}
          <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: isDark ? "#8b949e" : "#64748b", display: "inline-flex", alignItems: "center" }}>
              <ApartmentOutlined style={{ marginRight: 4 }} />
              服务商:
            </span>
            {providers.map((p) => (
              <Tooltip key={p.name} title={`请求次数: ${p.request_count} 次`}>
                <span
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    padding: "1px 6px",
                    fontSize: 11,
                    fontFamily: "monospace",
                    borderRadius: 3,
                    border: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
                    background: isDark ? "#161b22" : "#ffffff",
                    color: isDark ? "#c9d1d9" : "#1e293b",
                  }}
                >
                  <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#0284c7", marginRight: 4 }} />
                  {p.name}: <b style={{ marginLeft: 3 }}>{formatSmartTokens(p.total_tokens)}</b>
                </span>
              </Tooltip>
            ))}
          </div>

          {/* 模型分布 */}
          <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 600, color: isDark ? "#8b949e" : "#64748b", display: "inline-flex", alignItems: "center" }}>
              <AppstoreOutlined style={{ marginRight: 4 }} />
              模型:
            </span>
            {models.map((m) => (
              <span
                key={m.name}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  padding: "1px 6px",
                  fontSize: 11,
                  fontFamily: "monospace",
                  borderRadius: 3,
                  border: `1px solid ${isDark ? "#30363d" : "#e2e8f0"}`,
                  background: isDark ? "#161b22" : "#ffffff",
                  color: isDark ? "#c9d1d9" : "#1e293b",
                }}
              >
                <span style={{ width: 6, height: 6, borderRadius: "50%", background: "#9333ea", marginRight: 4 }} />
                {m.name}: <b style={{ marginLeft: 3 }}>{formatSmartTokens(m.total_tokens)}</b>
              </span>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
};
