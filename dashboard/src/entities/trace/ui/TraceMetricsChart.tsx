import React, { useState, useMemo } from "react";
import { Card, Segmented, Typography, Space, Tooltip, Tag, Empty } from "antd";
import ReactECharts from "echarts-for-react";
import {
  ClockCircleOutlined,
  DashboardOutlined,
  LineChartOutlined,
  ThunderboltOutlined,
  InfoCircleOutlined,
  BranchesOutlined,
} from "@ant-design/icons";
import { TraceRecord, TraceSpan } from "../model/types";
import { formatStageName, formatDuration } from "../../../shared/lib/formatters";
import { useTheme } from "../../../shared/lib/useTheme";

const { Text } = Typography;

interface TraceMetricsChartProps {
  trace: TraceRecord;
}

type MetricsViewMode = "duration" | "memory" | "dataflow";
type PipelineMode = "effective" | "all";

interface ProcessedSpanItem {
  rawSpan: TraceSpan;
  displayName: string;
  stageNameFormatted: string;
  durationMs: number;
  attemptIndex: number;
  totalAttempts: number;
  isRetry: boolean;
  isFinal: boolean;
}

export const TraceMetricsChart: React.FC<TraceMetricsChartProps> = ({ trace }) => {
  const { isDark } = useTheme();
  const [viewMode, setViewMode] = useState<MetricsViewMode>("duration");
  const [pipelineMode, setPipelineMode] = useState<PipelineMode>("effective");

  const spans: TraceSpan[] = useMemo(() => trace.spans || [], [trace.spans]);
  const perf = trace.performance_metrics;

  // 阶段调用频次与重试统计聚合 (Stage Stats & Retry Overhead)
  const stageStats = useMemo(() => {
    const stats = new Map<
      string,
      {
        attempts: TraceSpan[];
        totalDuration: number;
        retryOverhead: number;
      }
    >();

    for (const span of spans) {
      const existing = stats.get(span.stage_name);
      const dur = span.duration_ms ?? 0;
      if (!existing) {
        stats.set(span.stage_name, {
          attempts: [span],
          totalDuration: dur,
          retryOverhead: 0,
        });
      } else {
        existing.attempts.push(span);
        existing.totalDuration += dur;
        existing.retryOverhead = existing.attempts
          .slice(0, -1)
          .reduce((sum, s) => sum + (s.duration_ms ?? 0), 0);
      }
    }
    return stats;
  }, [spans]);

  // 判断是否包含断点续跑/重试阶段
  const hasRetries = useMemo(() => {
    for (const [, stat] of stageStats) {
      if (stat.attempts.length > 1) return true;
    }
    return false;
  }, [stageStats]);

  // 汇总重试开销与阶段信息
  const retrySummary = useMemo(() => {
    let totalOverheadMs = 0;
    const retriedStages: string[] = [];
    for (const [stage, stat] of stageStats) {
      if (stat.attempts.length > 1) {
        totalOverheadMs += stat.retryOverhead;
        retriedStages.push(`${formatStageName(stage)} (${stat.attempts.length}次)`);
      }
    }
    return {
      totalOverheadMs,
      retriedStages,
      summaryText: retriedStages.join("、"),
    };
  }, [stageStats]);

  // 全量阶段明细（按时间顺序消歧，避免 ECharts 同名 category 重叠碰撞）
  const processedAllSpans: ProcessedSpanItem[] = useMemo(() => {
    const stageAttemptCounters = new Map<string, number>();

    return spans.map((span) => {
      const stat = stageStats.get(span.stage_name);
      const totalAttempts = stat?.attempts.length || 1;
      const currentAttemptIdx = (stageAttemptCounters.get(span.stage_name) || 0) + 1;
      stageAttemptCounters.set(span.stage_name, currentAttemptIdx);

      const isRetry = currentAttemptIdx > 1;
      const isFinal = currentAttemptIdx === totalAttempts;
      const baseFormatted = formatStageName(span.stage_name);

      let displayName = baseFormatted;
      if (totalAttempts > 1) {
        if (currentAttemptIdx === 1) {
          displayName = `${baseFormatted} #1 (初次${span.status === "failed" ? "·失败" : ""})`;
        } else if (isFinal) {
          displayName = `${baseFormatted} #${currentAttemptIdx} (${span.status === "success" ? "续跑·成功" : "续跑·最终"})`;
        } else {
          displayName = `${baseFormatted} #${currentAttemptIdx} (重试${span.status === "failed" ? "·失败" : ""})`;
        }
      }

      return {
        rawSpan: span,
        displayName,
        stageNameFormatted: baseFormatted,
        durationMs: span.duration_ms ?? 0,
        attemptIndex: currentAttemptIdx,
        totalAttempts,
        isRetry,
        isFinal,
      };
    });
  }, [spans, stageStats]);

  // 精简有效流水线（每个阶段仅展示最终有效 Span，并汇总前序重试耗时）
  const effectiveSpans: ProcessedSpanItem[] = useMemo(() => {
    const list: ProcessedSpanItem[] = [];

    for (const [stageName, stat] of stageStats) {
      const latestSpan = stat.attempts[stat.attempts.length - 1];
      const totalAttempts = stat.attempts.length;
      const baseFormatted = formatStageName(stageName);

      list.push({
        rawSpan: latestSpan,
        displayName: baseFormatted,
        stageNameFormatted: baseFormatted,
        durationMs: latestSpan.duration_ms ?? 0,
        attemptIndex: totalAttempts,
        totalAttempts,
        isRetry: totalAttempts > 1,
        isFinal: true,
      });
    }

    return list;
  }, [stageStats]);

  // 当前激活展示的 Span 列表
  const currentSpans = useMemo(() => {
    if (!hasRetries || pipelineMode === "effective") {
      return effectiveSpans;
    }
    return processedAllSpans;
  }, [hasRetries, pipelineMode, effectiveSpans, processedAllSpans]);

  // 1. 阶段耗时瀑布 / 柱状图 Option
  const durationChartOption = useMemo(() => {
    const stageNames = currentSpans.map((s) => s.displayName);
    const durations = currentSpans.map((s) => s.durationMs);
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
          const item = currentSpans[idx];
          if (!item) return "";
          const s = item.rawSpan;
          const dur = item.durationMs;
          const pct = ((dur / totalMs) * 100).toFixed(1);

          const stat = stageStats.get(s.stage_name);
          const attemptsCount = stat?.attempts.length || 1;
          const retryOverhead = stat?.retryOverhead || 0;

          let retryHtml = "";
          if (pipelineMode === "effective" && attemptsCount > 1) {
            retryHtml = `
              <div style="margin-top: 4px; padding-top: 4px; border-top: 1px dashed ${isDark ? "#30363d" : "#e2e8f0"}; font-size: 11px; color: #ea580c;">
                ⚠️ 该阶段共执行 <b>${attemptsCount}</b> 次 (累计前序重试损耗: ${(retryOverhead / 1000).toFixed(2)}s)
              </div>
            `;
          }

          return `
            <div style="font-weight: 600; font-size: 12px; margin-bottom: 4px; color: ${isDark ? "#ffffff" : "#0f172a"};">
              ${item.displayName}
            </div>
            <div style="font-size: 12px; color: #2563eb; margin-bottom: 2px;">
              ${pipelineMode === "effective" && attemptsCount > 1 ? "有效耗时" : "阶段耗时"}: <b style="font-family: monospace;">${dur.toLocaleString()} ms</b> (${pct}%)
            </div>
            <div style="font-size: 11px; color: ${isDark ? "#8b949e" : "#64748b"};">
              执行状态: <b>${s.status}</b> ${pipelineMode === "all" && item.totalAttempts > 1 ? `(第 ${item.attemptIndex}/${item.totalAttempts} 次尝试)` : ""}
            </div>
            ${retryHtml}
          `;
        },
      },
      grid: {
        top: 12,
        right: 25,
        bottom: 25,
        left: 10,
        containLabel: true,
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
          data: currentSpans.map((item) => {
            const s = item.rawSpan;
            const val = item.durationMs;
            let barColor = "#2563eb";
            if (s.status === "failed" || s.status === "error") barColor = "#dc2626";
            else if (s.status === "warning") barColor = "#ea580c";
            else if (item.isRetry && !item.isFinal) barColor = "#f59e0b";
            else if (val > 10000) barColor = "#2563eb";
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
  }, [currentSpans, trace.duration_ms, isDark, pipelineMode, stageStats]);

  // 2. 内存 RSS 演进面积图 Option
  const memoryChartOption = useMemo(() => {
    const labels: string[] = ["起点 (Init)"];
    const memValues: number[] = [perf?.init_memory_mb || 0];

    const sourceSpans = pipelineMode === "effective" ? effectiveSpans : processedAllSpans;

    sourceSpans.forEach((item) => {
      labels.push(item.displayName);
      const endMem =
        item.rawSpan.end_memory_mb ??
        (item.rawSpan.payload?.end_memory_mb as number) ??
        memValues[memValues.length - 1];
      memValues.push(Number(endMem) || 0);
    });

    if (perf?.final_memory_mb && memValues[memValues.length - 1] !== perf.final_memory_mb) {
      labels.push("终态 (Final)");
      memValues.push(perf.final_memory_mb);
    }

    const peakMem = perf?.peak_memory_mb || Math.max(...memValues, 1);
    const positiveMemValues = memValues.filter((v) => v > 0);
    const minMem =
      positiveMemValues.length > 0
        ? Math.max(0, Math.floor(Math.min(...positiveMemValues) * 0.9))
        : 0;

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
        right: 25,
        bottom: 25,
        left: 10,
        containLabel: true,
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
  }, [pipelineMode, effectiveSpans, processedAllSpans, perf, isDark]);

  // 3. 数据流转与 Base64 体积膨胀对比 Option
  const dataflowChartOption = useMemo(() => {
    const renderSpan = [...spans].reverse().find((s) => s.stage_name === "RENDER_REPORT");
    const dispatchSpan = [...spans].reverse().find((s) => s.stage_name === "DISPATCH_REPORT");

    const htmlKb = Number(renderSpan?.payload?.html_size_kb || 0);
    const rawImageBytes = Number(renderSpan?.payload?.image_bytes || 0);
    const rawImageKb =
      rawImageBytes > 0
        ? Number((rawImageBytes / 1024).toFixed(1))
        : Number(dispatchSpan?.payload?.raw_image_kb || 0);
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
        right: 25,
        bottom: 25,
        left: 10,
        containLabel: true,
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
            {
              value: isB64 ? b64Kb : rawImageKb,
              itemStyle: { color: isB64 ? "#f59e0b" : "#10b981", borderRadius: [4, 4, 0, 0] },
            },
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

  const hasMetrics =
    spans.length > 0 ||
    Boolean(perf?.peak_memory_mb) ||
    Boolean(perf?.init_memory_mb);

  // 动态计算图表高度，保证条目较多时不拥挤
  const chartHeight = useMemo(() => {
    if (viewMode === "duration") {
      return Math.max(150, Math.min(320, currentSpans.length * 26 + 35));
    }
    return 150;
  }, [viewMode, currentSpans.length]);

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

        <Space size={6} wrap>
          {hasRetries && (
            <Segmented
              size="small"
              value={pipelineMode}
              onChange={(val) => setPipelineMode(val as PipelineMode)}
              options={[
                {
                  label: "精简链路",
                  value: "effective",
                  icon: <BranchesOutlined />,
                },
                {
                  label: `全量重试 (${spans.length})`,
                  value: "all",
                },
              ]}
            />
          )}

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
        </Space>
      </div>

      {/* KPI 指标栏 */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "center",
          gap: 6,
          marginBottom: 8,
          padding: "4px 8px",
          background: isDark ? "#161b22" : "#ffffff",
          borderRadius: 4,
          border: `1px solid ${isDark ? "#21262d" : "#f1f5f9"}`,
        }}
      >
        <span style={{ fontSize: 11, color: isDark ? "#8b949e" : "#64748b" }}>
          有效耗时: <b style={{ color: isDark ? "#f0f6fc" : "#0f172a", fontFamily: "monospace" }}>{trace.duration_ms ? `${(trace.duration_ms / 1000).toFixed(2)}s` : "计算中"}</b>
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
        {hasRetries && (
          <>
            <span style={{ color: isDark ? "#30363d" : "#e2e8f0" }}>|</span>
            <Tooltip title={`检测到任务包含断点续跑或阶段重试 (${retrySummary.summaryText})，累计产生约 ${(retrySummary.totalOverheadMs / 1000).toFixed(2)}s 前序重试开销`}>
              <Tag
                color="volcano"
                style={{ margin: 0, padding: "0 6px", fontSize: 10, lineHeight: "16px", height: 16, cursor: "pointer" }}
              >
                重试损耗: +{(retrySummary.totalOverheadMs / 1000).toFixed(1)}s ({retrySummary.retriedStages.length}个阶段发生重试)
              </Tag>
            </Tooltip>
          </>
        )}
      </div>

      {/* 图表展示区域 */}
      <div style={{ width: "100%", minHeight: chartHeight }}>
        {viewMode === "duration" && (
          <ReactECharts
            option={durationChartOption}
            style={{ height: chartHeight, width: "100%" }}
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

