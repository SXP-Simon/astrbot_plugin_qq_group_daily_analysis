import React, { useState, useEffect } from "react";
import { Row, Col, Card, Empty, Typography, Space, Segmented, Tag, Tooltip } from "antd";
import ReactECharts from "echarts-for-react";
import {
  AreaChartOutlined,
  BarChartOutlined,
  ApiOutlined,
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
      backgroundColor: isDark ? "rgba(24, 24, 28, 0.96)" : "rgba(255, 255, 255, 0.96)",
      borderColor: isDark ? "#383838" : "#f0f0f0",
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: isDark ? "#e6edf3" : "#262626", fontSize: 12 },
      formatter: (params: Array<{ dataIndex: number; value: number }>) => {
        if (!params || params.length === 0) return "";
        const idx = params[0].dataIndex;
        const item = points[idx];
        if (!item) return "";
        return `
          <div style="font-weight: 600; font-size: 12px; margin-bottom: 6px; color: ${isDark ? "#ffffff" : "#262626"};">
            📅 ${item.date_full || item.date}
          </div>
          <div style="font-size: 12px; color: #1677ff; margin-bottom: 3px;">
            分析触发次数: <b>${item.request_count}</b> 次
          </div>
          <div style="font-size: 11px; color: #52c41a;">
            成功: ${item.succeeded_count} 次 / 失败: <span style="color: ${item.failed_count > 0 ? "#ff4d4f" : "#8c8c8c"}">${item.failed_count} 次</span>
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
      axisLine: { lineStyle: { color: isDark ? "#303030" : "#e8e8e8" } },
      axisTick: { show: false },
      axisLabel: {
        color: isDark ? "#8c8c8c" : "#8c8c8c",
        fontSize: 11,
      },
    },
    yAxis: {
      type: "value",
      minInterval: 1,
      splitLine: {
        lineStyle: {
          color: isDark ? "#262626" : "#f0f0f0",
          type: "dashed",
        },
      },
      axisLabel: {
        color: isDark ? "#8c8c8c" : "#8c8c8c",
        fontSize: 11,
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
          width: 2.5,
          color: "#1677ff",
        },
        itemStyle: {
          color: "#1677ff",
        },
        areaStyle: {
          color: {
            type: "linear",
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: "rgba(22, 119, 255, 0.55)" },
              { offset: 0.8, color: "rgba(22, 119, 255, 0.1)" },
              { offset: 1, color: "rgba(22, 119, 255, 0.0)" },
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
      backgroundColor: isDark ? "rgba(24, 24, 28, 0.96)" : "rgba(255, 255, 255, 0.96)",
      borderColor: isDark ? "#383838" : "#f0f0f0",
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: isDark ? "#e6edf3" : "#262626", fontSize: 12 },
      formatter: (params: Array<{ dataIndex: number }>) => {
        if (!params || params.length === 0) return "";
        const idx = params[0].dataIndex;
        const item = points[idx];
        if (!item) return "";
        return `
          <div style="font-weight: 600; font-size: 12px; margin-bottom: 6px; color: ${isDark ? "#ffffff" : "#262626"};">
            📅 ${item.date_full || item.date}
          </div>
          <div style="font-size: 12px; color: #1677ff; margin-bottom: 3px;">
            总消耗: <b>${formatTokens(item.total_tokens)}</b>
          </div>
          <div style="font-size: 11px; color: ${isDark ? "#bfbfbf" : "#595959"};">
            输入 (Prompt): ${formatTokens(item.prompt_tokens)}
          </div>
          <div style="font-size: 11px; color: ${isDark ? "#bfbfbf" : "#595959"};">
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
      axisLine: { lineStyle: { color: isDark ? "#303030" : "#e8e8e8" } },
      axisTick: { show: false },
      axisLabel: {
        color: isDark ? "#8c8c8c" : "#8c8c8c",
        fontSize: 11,
      },
    },
    yAxis: {
      type: "value",
      splitLine: {
        lineStyle: {
          color: isDark ? "#262626" : "#f0f0f0",
          type: "dashed",
        },
      },
      axisLabel: {
        color: isDark ? "#8c8c8c" : "#8c8c8c",
        fontSize: 11,
        formatter: (val: number) => (val >= 1000 ? `${Math.round(val / 1000)}k` : `${val}`),
      },
    },
    series: [
      {
        name: "输入 Tokens",
        type: "bar",
        stack: "tokens",
        barMaxWidth: 20,
        itemStyle: {
          color: "#1677ff",
        },
        data: promptTokens,
      },
      {
        name: "输出 Tokens",
        type: "bar",
        stack: "tokens",
        barMaxWidth: 20,
        itemStyle: {
          color: "#69b1ff",
          borderRadius: [3, 3, 0, 0],
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
          <Space size={8}>
            <AreaChartOutlined style={{ color: "#1677ff" }} />
            <Text strong style={{ fontSize: 13 }}>
              分析行为与 Token 消耗可观测趋势
            </Text>
          </Space>

          {/* 时间粒度与跨度视图切换控制器 */}
          <Segmented
            size="small"
            value={selectedRange}
            onChange={(v) => handleRangeChange(v as RangeOption)}
            options={[
              { label: "近48小时 (按小时)", value: "48h" },
              { label: "近7天 (一周)", value: "7d" },
              { label: "近14天", value: "14d" },
              { label: "近30天", value: "30d" },
            ]}
          />
        </div>
      }
    >
      <Row gutter={[12, 12]}>
        {/* API 请求次数面积图 */}
        <Col xs={24} md={12}>
          <div
            style={{
              padding: "8px 12px",
              background: isDark ? "#141414" : "#fafafa",
              borderRadius: 6,
              border: `1px solid ${isDark ? "#262626" : "#f0f0f0"}`,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <Text strong style={{ fontSize: 13 }}>
                API 请求次数
              </Text>
              <Text strong style={{ fontSize: 14, color: "#1677ff" }}>
                {rangeTotalRequests > 0 ? rangeTotalRequests.toLocaleString() : totalTraces.toLocaleString()} 次
              </Text>
            </div>

            {hasData ? (
              <ReactECharts
                option={requestChartOption}
                style={{ height: 170, width: "100%" }}
                opts={{ renderer: "svg" }}
                showLoading={currentLoading}
              />
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无请求趋势数据"
                style={{ height: 170, display: "flex", flexDirection: "column", justifyContent: "center" }}
              />
            )}
          </div>
        </Col>

        {/* Tokens 消耗柱状图 */}
        <Col xs={24} md={12}>
          <div
            style={{
              padding: "8px 12px",
              background: isDark ? "#141414" : "#fafafa",
              borderRadius: 6,
              border: `1px solid ${isDark ? "#262626" : "#f0f0f0"}`,
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
              <Text strong style={{ fontSize: 13 }}>
                <BarChartOutlined style={{ color: "#722ed1", marginRight: 6 }} />
                Tokens 消耗趋势
              </Text>
              <Text strong style={{ fontSize: 14, color: "#722ed1" }}>
                {rangeTotalTokens > 0 ? formatSmartTokens(rangeTotalTokens) : formatSmartTokens(totalTokens)}
              </Text>
            </div>

            {hasData ? (
              <ReactECharts
                option={tokenChartOption}
                style={{ height: 170, width: "100%" }}
                opts={{ renderer: "svg" }}
                showLoading={currentLoading}
              />
            ) : (
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description="暂无 Token 消耗趋势数据"
                style={{ height: 170, display: "flex", flexDirection: "column", justifyContent: "center" }}
              />
            )}
          </div>
        </Col>
      </Row>

      {/* 服务商 (Provider) 与模型 (Model ID) 细粒度审计统计条 */}
      {(providers.length > 0 || models.length > 0) && (
        <div
          style={{
            marginTop: 12,
            paddingTop: 10,
            borderTop: `1px dashed ${isDark ? "#282828" : "#f0f0f0"}`,
            display: "flex",
            flexWrap: "wrap",
            justifyContent: "space-between",
            alignItems: "center",
            gap: 8,
          }}
        >
          {/* 服务商分布 */}
          <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
            <Text type="secondary" style={{ fontSize: 11, fontWeight: 600 }}>
              <ApiOutlined style={{ marginRight: 4 }} />
              服务商分布:
            </Text>
            {providers.map((p) => (
              <Tooltip key={p.name} title={`请求次数: ${p.request_count} 次`}>
                <Tag color="cyan" style={{ fontSize: 11, margin: 0 }}>
                  {p.name}: <b>{formatSmartTokens(p.total_tokens)}</b>
                </Tag>
              </Tooltip>
            ))}
          </div>

          {/* 模型分布 */}
          <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 6 }}>
            <Text type="secondary" style={{ fontSize: 11, fontWeight: 600 }}>
              <AppstoreOutlined style={{ marginRight: 4 }} />
              模型分布:
            </Text>
            {models.map((m) => (
              <Tag key={m.name} color="purple" style={{ fontSize: 11, margin: 0 }}>
                {m.name}: <b>{formatSmartTokens(m.total_tokens)}</b>
              </Tag>
            ))}
          </div>
        </div>
      )}
    </Card>
  );
};
