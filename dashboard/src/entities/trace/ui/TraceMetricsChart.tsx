import React, { useState, useMemo } from "react";
import { Card, Segmented, Typography, Space, Tooltip, Tag, Empty } from "antd";
import ReactECharts from "echarts-for-react";
import {
  ClockCircleOutlined,
  DashboardOutlined,
  LineChartOutlined,
  ThunderboltOutlined,
  InfoCircleOutlined,
} from "@ant-design/icons";
import { TraceRecord, TraceSpan } from "../model/types";
import { formatStageName } from "../../../shared/lib/formatters";
import { useTheme } from "../../../shared/lib/useTheme";

const { Text } = Typography;

interface TraceMetricsChartProps {
  trace: TraceRecord;
}

type MetricsViewMode = "duration" | "memory" | "dataflow";

export const TraceMetricsChart: React.FC<TraceMetricsChartProps> = ({ trace }) => {
  const { isDark } = useTheme();
  const [viewMode, setViewMode] = useState<MetricsViewMode>("duration");

  const spans: TraceSpan[] = useMemo(() => trace.spans || [], [trace.spans]);
  const perf = trace.performance_metrics;

  // 1. 阶段耗时瀑布 / 柱状图 Option
  const durationChartOption = useMemo(() => {
    const stageNames = spans.map((s) => formatStageName(s.stage_name));
    const durations = spans.map((s) => s.duration_ms ?? 0);
    const totalMs = durations.reduce((acc, v) => acc + v, 0) || trace.duration_ms || 1;

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: isDark ? "rgba(22, 27, 34, 0.96)" : "rgba(255, 255, 255, 0.98)",
        borderColor: isDark ? "#30363d" : "#e2e8f0",
        borderWidth: 1,
        padding: [8, 12],
        textStyle: { color: isDark ? "#c9d1d9" : "#1e293b", fontSize: 12 },
        formatter: (params: Array<{ dataIndex: number }>) => {
          if (!params || params.length === 0) return "";
          const idx = params[0].dataIndex;
          const s = spans[idx];
          if (!s) return "";
          const dur = s.duration_ms ?? 0;
          const pct = ((dur / totalMs) * 100).toFixed(1);
          return `
            <div style="font-weight: 600; font-size: 12px; margin-bottom: 4px; color: ${isDark ? "#ffffff" : "#0f172a"};">
              ${formatStageName(s.stage_name)}
            </div>
            <div style="font-size: 12px; color: #2563eb; margin-bottom: 2px;">
              阶段耗时: <b style="font-family: monospace;">${dur.toLocaleString()} ms</b> (${pct}%)
            </div>
            <div style="font-size: 11px; color: ${isDark ? "#8b949e" : "#64748b"};">
              状态: <b>${s.status}</b>
            </div>
          `;
        },
      },
      grid: {
        top: 15,
        right: 20,
        bottom: 25,
        left: 80,
        containLabel: false,
      },
      xAxis: {
        type: "value",
        splitLine: {
          lineStyle: {
            color: isDark ? "#21262d" : "#f1f5f9",
            type: "dashed",
          },
        },
        axisLabel: {
          color: isDark ? "#8b949e" : "#64748b",
          fontSize: 10,
          fontFamily: "'JetBrains Mono', Consolas, sans-serif",
          formatter: (val: number) => (val >= 1000 ? `${(val / 1000).toFixed(1)}s` : `${val}ms`),
        },
      },
      yAxis: {
        type: "category",
        data: stageNames,
        axisLine: { lineStyle: { color: isDark ? "#30363d" : "#e2e8f0" } },
        axisTick: { show: false },
        axisLabel: {
          color: isDark ? "#8b949e" : "#475569",
          fontSize: 11,
        },
      },
      series: [
        {
          name: "耗时",
          type: "bar",
          data: durations.map((val, idx) => {
            const s = spans[idx];
            let barColor = "#2563eb";
            if (s?.status === "failed") barColor = "#dc2626";
            else if (s?.status === "warning") barColor = "#ea580c";
            else if (val > 10000) barColor = "#f59e0b";
            return {
              value: val,
              itemStyle: {
                color: barColor,
                borderRadius: [0, 4, 4, 0],
              },
            };
          }),
        },
      ],
    };
  }, [spans, trace.duration_ms, isDark]);

  // 2. 内存 RSS 演进面积图 Option
  const memoryChartOption = useMemo(() => {
    const labels: string[] = ["起点 (Init)"];
    const memValues: number[] = [perf?.init_memory_mb || 0];

    spans.forEach((s) => {
      labels.push(formatStageName(s.stage_name));
      const endMem = s.end_memory_mb ?? (s.payload?.end_memory_mb as number) ?? memValues[memValues.length - 1];
      memValues.push(Number(endMem) || 0);
    });

    if (perf?.final_memory_mb && memValues[memValues.length - 1] !== perf.final_memory_mb) {
      labels.push("终态 (Final)");
      memValues.push(perf.final_memory_mb);
    }

    const peakMem = perf?.peak_memory_mb || Math.max(...memValues, 1);
    const minMem = Math.max(0, Math.floor(Math.min(...memValues.filter((v) => v > 0)) * 0.9));

    return {
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
          const stageName = labels[idx];
          const curVal = memValues[idx];
          const prevVal = idx > 0 ? memValues[idx - 1] : curVal;
          const delta = (curVal - prevVal).toFixed(2);
          const deltaColor = Number(delta) > 0 ? "#dc2626" : Number(delta) < 0 ? "#16a34a" : "#64748b";

          return `
            <div style="font-weight: 600; font-size: 12px; margin-bottom: 4px; color: ${isDark ? "#ffffff" : "#0f172a"};">
              ${stageName}
            </div>
            <div style="font-size: 12px; color: #0d9488; margin-bottom: 2px;">
              当前进程 RSS: <b style="font-family: monospace;">${curVal.toFixed(1)} MB</b>
            </div>
            <div style="font-size: 11px; color: ${deltaColor};">
              阶段内存增量: <b>${Number(delta) > 0 ? `+${delta}` : delta} MB</b>
            </div>
          `;
        },
      },
      grid: {
        top: 20,
        right: 20,
        bottom: 25,
        left: 45,
        containLabel: false,
      },
      xAxis: {
        type: "category",
        data: labels,
        axisLine: { lineStyle: { color: isDark ? "#30363d" : "#e2e8f0" } },
        axisTick: { show: false },
        axisLabel: {
          color: isDark ? "#8b949e" : "#64748b",
          fontSize: 10,
        },
      },
      yAxis: {
        type: "value",
        min: minMem,
        splitLine: {
          lineStyle: {
            color: isDark ? "#21262d" : "#f1f5f9",
            type: "dashed",
          },
        },
        axisLabel: {
          color: isDark ? "#8b949e" : "#64748b",
          fontSize: 10,
          fontFamily: "'JetBrains Mono', Consolas, sans-serif",
          formatter: "{value}M",
        },
      },
      series: [
        {
          name: "内存 RSS",
          type: "line",
          smooth: true,
          showSymbol: true,
          symbolSize: 5,
          data: memValues,
          lineStyle: {
            width: 2,
            color: "#0d9488",
          },
          itemStyle: {
            color: "#0d9488",
          },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: "rgba(13, 148, 136, 0.4)" },
                { offset: 1, color: "rgba(13, 148, 136, 0.02)" },
              ],
            },
          },
          markLine: {
            symbol: ["none", "none"],
            label: {
              formatter: "峰值: {c} MB",
              position: "insideEndTop",
              fontSize: 10,
              color: isDark ? "#fbbf24" : "#d97706",
            },
            lineStyle: {
              color: isDark ? "#fbbf24" : "#d97706",
              type: "dotted",
              width: 1.5,
            },
            data: [{ yAxis: peakMem }],
          },
        },
      ],
    };
  }, [spans, perf, isDark]);

  // 3. 数据流转与 Base64 体积膨胀对比 Option
  const dataflowChartOption = useMemo(() => {
    const renderSpan = spans.find((s) => s.stage_name === "RENDER_REPORT");
    const dispatchSpan = spans.find((s) => s.stage_name === "DISPATCH_REPORT");

    const htmlKb = Number(renderSpan?.payload?.html_size_kb || 0);
    const rawImageBytes = Number(renderSpan?.payload?.image_bytes || 0);
    const rawImageKb = rawImageBytes > 0 ? Number((rawImageBytes / 1024).toFixed(1)) : Number(dispatchSpan?.payload?.raw_image_kb || 0);
    const b64Kb = Number(dispatchSpan?.payload?.base64_payload_kb || 0);
    const isB64 = dispatchSpan?.payload?.transmission_mode === "base64" || b64Kb > 0;

    const categories = ["HTML 源码", "原始图片", isB64 ? "Base64 传输流 (+33%)" : "网络传输载荷"];
    const values = [htmlKb, rawImageKb, isB64 ? b64Kb : rawImageKb];

    return {
      backgroundColor: "transparent",
      tooltip: {
        trigger: "axis",
        axisPointer: { type: "shadow" },
        backgroundColor: isDark ? "rgba(22, 27, 34, 0.96)" : "rgba(255, 255, 255, 0.98)",
        borderColor: isDark ? "#30363d" : "#e2e8f0",
        borderWidth: 1,
        padding: [8, 12],
        textStyle: { color: isDark ? "#c9d1d9" : "#1e293b", fontSize: 12 },
        formatter: (params: Array<{ dataIndex: number }>) => {
          if (!params || params.length === 0) return "";
          const idx = params[0].dataIndex;
          const cat = categories[idx];
          const val = values[idx];
          return `
            <div style="font-weight: 600; font-size: 12px; margin-bottom: 4px; color: ${isDark ? "#ffffff" : "#0f172a"};">
              ${cat}
            </div>
            <div style="font-size: 12px; color: #7c3aed;">
              体积大小: <b style="font-family: monospace;">${val.toFixed(1)} KB</b>
            </div>
            ${idx === 2 && isB64 ? '<div style="font-size: 11px; color: #ea580c; margin-top: 2px;">⚠️ Base64 编码引入了约 33% 的网络传输膨胀</div>' : ""}
          `;
        },
      },
      grid: {
        top: 20,
        right: 20,
        bottom: 25,
        left: 50,
        containLabel: false,
      },
      xAxis: {
        type: "category",
        data: categories,
        axisLine: { lineStyle: { color: isDark ? "#30363d" : "#e2e8f0" } },
        axisTick: { show: false },
        axisLabel: {
          color: isDark ? "#8b949e" : "#64748b",
          fontSize: 10,
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
          fontSize: 10,
          fontFamily: "'JetBrains Mono', Consolas, sans-serif",
          formatter: "{value} KB",
        },
      },
      series: [
        {
          name: "体积",
          type: "bar",
          barWidth: "35%",
          data: [
            { value: htmlKb, itemStyle: { color: "#3b82f6", borderRadius: [4, 4, 0, 0] } },
            { value: rawImageKb, itemStyle: { color: "#10b981", borderRadius: [4, 4, 0, 0] } },
            { value: isB64 ? b64Kb : rawImageKb, itemStyle: { color: isB64 ? "#f59e0b" : "#10b981", borderRadius: [4, 4, 0, 0] } },
          ],
        },
      ],
    };
  }, [spans, isDark]);

  const hasDataflowData = useMemo(() => {
    const renderSpan = spans.find((s) => s.stage_name === "RENDER_REPORT");
    const dispatchSpan = spans.find((s) => s.stage_name === "DISPATCH_REPORT");
    const htmlKb = Number(renderSpan?.payload?.html_size_kb || 0);
    const rawImageBytes = Number(renderSpan?.payload?.image_bytes || 0);
    const rawImageKb =
      rawImageBytes > 0
        ? Number((rawImageBytes / 1024).toFixed(1))
        : Number(dispatchSpan?.payload?.raw_image_kb || 0);
    const b64Kb = Number(dispatchSpan?.payload?.base64_payload_kb || 0);
    return htmlKb > 0 || rawImageKb > 0 || b64Kb > 0;
  }, [spans]);

  const hasMetrics = spans.length > 0 || Boolean(perf);

  if (!hasMetrics) return null;

  return (
    <Card
      size="small"
      style={{
        background: isDark ? "#0d1117" : "#f8fafc",
        borderColor: isDark ? "#30363d" : "#e2e8f0",
        borderRadius: 6,
      }}
      styles={{ body: { padding: "10px 12px" } }}
    >
      {/* 头部与视图切换器 */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 8,
          flexWrap: "wrap",
          gap: 6,
        }}
      >
        <Space size={6} align="center">
          <DashboardOutlined style={{ color: "#2563eb", fontSize: 13 }} />
          <Text strong style={{ fontSize: 12, color: isDark ? "#c9d1d9" : "#1e293b" }}>
            全链路性能指标与运行期资源观测
          </Text>
          <Tooltip title="精准采集各生命周期耗时瀑布、Python 进程 RSS 内存阶梯演进、T2I 渲染链路细分与 Base64 传输体积膨胀比">
            <InfoCircleOutlined style={{ color: isDark ? "#8b949e" : "#94a3b8", fontSize: 11, cursor: "pointer" }} />
          </Tooltip>
        </Space>

        <Segmented
          size="small"
          value={viewMode}
          onChange={(val) => setViewMode(val as MetricsViewMode)}
          options={[
            {
              label: "耗时瀑布",
              value: "duration",
              icon: <ClockCircleOutlined />,
            },
            {
              label: "内存演进",
              value: "memory",
              icon: <LineChartOutlined />,
            },
            {
              label: "数据与膨胀",
              value: "dataflow",
              icon: <ThunderboltOutlined />,
            },
          ]}
        />
      </div>

      {/* KPI 指标栏 */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 6,
          marginBottom: 8,
          padding: "4px 8px",
          background: isDark ? "#161b22" : "#ffffff",
          borderRadius: 4,
          border: `1px solid ${isDark ? "#21262d" : "#f1f5f9"}`,
        }}
      >
        <span style={{ fontSize: 11, color: isDark ? "#8b949e" : "#64748b" }}>
          总耗时: <b style={{ color: isDark ? "#f0f6fc" : "#0f172a", fontFamily: "monospace" }}>{trace.duration_ms ? `${(trace.duration_ms / 1000).toFixed(2)}s` : "计算中"}</b>
        </span>
        <span style={{ color: isDark ? "#30363d" : "#e2e8f0" }}>|</span>
        <span style={{ fontSize: 11, color: isDark ? "#8b949e" : "#64748b" }}>
          峰值内存: <b style={{ color: isDark ? "#f0f6fc" : "#0f172a", fontFamily: "monospace" }}>{perf?.peak_memory_mb ? `${perf.peak_memory_mb.toFixed(1)} MB` : "--"}</b>
        </span>
        {perf?.delta_memory_mb !== undefined && (
          <Tag
            color={perf.delta_memory_mb > 15 ? "orange" : "default"}
            style={{ margin: 0, padding: "0 4px", fontSize: 10, lineHeight: "16px", height: 16 }}
          >
            增量: {perf.delta_memory_mb > 0 ? `+${perf.delta_memory_mb.toFixed(1)}` : perf.delta_memory_mb.toFixed(1)} MB
          </Tag>
        )}
      </div>

      {/* 图表展示区域 */}
      <div style={{ width: "100%", height: 150 }}>
        {viewMode === "duration" && (
          <ReactECharts
            option={durationChartOption}
            style={{ height: 150, width: "100%" }}
            opts={{ renderer: "svg" }}
          />
        )}
        {viewMode === "memory" && (
          <ReactECharts
            option={memoryChartOption}
            style={{ height: 150, width: "100%" }}
            opts={{ renderer: "svg" }}
          />
        )}
        {viewMode === "dataflow" &&
          (hasDataflowData ? (
            <ReactECharts
              option={dataflowChartOption}
              style={{ height: 150, width: "100%" }}
              opts={{ renderer: "svg" }}
            />
          ) : (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: 150,
              }}
            >
              <Empty
                image={Empty.PRESENTED_IMAGE_SIMPLE}
                description={
                  <span style={{ color: isDark ? "#8b949e" : "#94a3b8", fontSize: 11 }}>
                    当前报告未产生图片或 Base64 媒体载荷数据（纯文本或未开启图片输出）
                  </span>
                }
                style={{ margin: 0 }}
              />
            </div>
          ))}
      </div>
    </Card>
  );
};
