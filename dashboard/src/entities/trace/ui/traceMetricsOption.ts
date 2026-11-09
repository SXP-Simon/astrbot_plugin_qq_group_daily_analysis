import type { EChartsOption } from "echarts";
import type { MetricsViewMode, TraceMetrics } from "@/entities/trace/model/traceMetrics";

interface ChartPalette {
  text: string;
  muted: string;
  border: string;
  background: string;
  accent: string;
  danger: string;
}

export function createTraceMetricsOption(
  metrics: TraceMetrics,
  mode: MetricsViewMode,
  colors: ChartPalette,
): EChartsOption {
  const duration = mode === "duration";
  const memory = mode === "memory";
  const labels = duration
    ? metrics.stages.map(
        (item) => `${"  ".repeat(item.depth)}${item.depth ? "↳ " : ""}${item.label}`,
      )
    : memory
      ? metrics.memory.map((item) => item.label)
      : metrics.dataflow.map((item) => item.label);
  const values = duration
    ? metrics.stages.map((item) => item.durationMs)
    : memory
      ? metrics.memory.map((item) => item.rss)
      : metrics.dataflow.map((item) => item.sizeKb);
  const unit = duration ? "ms" : memory ? "MiB" : "KB";
  const categoryAxis = {
    type: "category" as const,
    data: labels,
    axisLine: { lineStyle: { color: colors.border } },
    axisTick: { show: false },
    axisLabel: {
      color: colors.muted,
      fontSize: 11,
      width: duration ? 210 : 90,
      overflow: "truncate" as const,
    },
  };
  const valueAxis = {
    type: "value" as const,
    splitLine: { lineStyle: { color: colors.border, type: "dashed" as const } },
    axisLabel: { color: colors.muted, fontSize: 11, formatter: `{value} ${unit}` },
  };
  return {
    animation: false,
    backgroundColor: "transparent",
    textStyle: { fontFamily: '"LXGW WenKai Screen", sans-serif', color: colors.text },
    aria: { enabled: true },
    grid: { top: 20, right: 30, bottom: 30, left: 8, containLabel: true },
    xAxis: duration ? valueAxis : categoryAxis,
    yAxis: duration ? { ...categoryAxis, inverse: true } : valueAxis,
    tooltip: {
      trigger: "item",
      renderMode: "html",
      enterable: false,
      transitionDuration: 0,
      extraCssText: "pointer-events: none; white-space: pre-wrap;",
      confine: true,
      backgroundColor: colors.background,
      borderColor: colors.border,
      textStyle: { color: colors.text, fontSize: 12 },
      formatter: (params: unknown) => {
        if (
          !params ||
          typeof params !== "object" ||
          !("dataIndex" in params) ||
          typeof params.dataIndex !== "number"
        )
          return "";
        const index = params.dataIndex;
        const value = values[index];
        let text = `${labels[index]}\n${value == null ? "未记录" : `${value.toLocaleString()} ${unit}`}`;
        if (duration) {
          const item = metrics.stages[index];
          if (item) {
            if (item.ratio !== null) text += `\n占${item.denominator} ${item.ratio.toFixed(1)}%`;
            text += `\n状态：${item.span.status}`;
          }
        } else if (memory) {
          const delta = metrics.memory[index]?.delta;
          if (delta != null)
            text += `\n相邻采样净变化：${delta > 0 ? "+" : ""}${delta.toFixed(1)} MiB`;
        }
        const element = document.createElement("div");
        element.textContent = text;
        return element;
      },
    },
    series: memory
      ? [
          {
            name: "宿主 RSS",
            type: "line",
            data: values,
            connectNulls: false,
            smooth: false,
            symbolSize: 6,
            itemStyle: { color: colors.accent },
            lineStyle: { color: colors.accent },
            markLine:
              metrics.peakMemoryMb !== null
                ? {
                    symbol: ["none", "none"],
                    label: {
                      formatter: "宿主记录峰值：{c} MiB",
                      color: colors.muted,
                      fontSize: 11,
                    },
                    lineStyle: { color: colors.muted, type: "dashed" },
                    data: [{ yAxis: metrics.peakMemoryMb }],
                  }
                : undefined,
          },
        ]
      : [
          {
            name: duration ? "阶段耗时" : "传输体积",
            type: "bar",
            barMaxWidth: 24,
            data: values.map((value, index) => ({
              value,
              itemStyle: {
                color:
                  duration && ["failed", "error"].includes(metrics.stages[index]?.span.status)
                    ? colors.danger
                    : colors.accent,
                borderRadius: 3,
              },
            })),
          },
        ],
  };
}
