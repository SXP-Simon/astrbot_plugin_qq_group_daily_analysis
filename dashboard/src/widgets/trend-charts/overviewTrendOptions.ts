import type { EChartsOption } from "echarts";
import type { AnalyticsTrendPoint, ProviderBreakdownItem } from "../../entities/metric/model/types";

interface Palette {
  text: string;
  muted: string;
  border: string;
  background: string;
  accent: string;
  providerColors: string[];
}

export function createOverviewTrendOptions(
  points: AnalyticsTrendPoint[],
  providers: ProviderBreakdownItem[],
  colors: Palette,
): EChartsOption[] {
  const tooltip = {
    renderMode: "richText" as const,
    confine: true,
    backgroundColor: colors.background,
    borderColor: colors.border,
    textStyle: { color: colors.text, fontSize: 12 },
  };
  const common: EChartsOption = {
    animation: false,
    backgroundColor: "transparent",
    aria: { enabled: true },
    textStyle: { fontFamily: '"LXGW WenKai Screen", sans-serif', color: colors.text },
    grid: { top: 26, bottom: 28, left: 8, right: 14, containLabel: true },
    xAxis: {
      type: "category",
      data: points.map((point) => point.date),
      axisTick: { show: false },
      axisLine: { lineStyle: { color: colors.border } },
      axisLabel: { color: colors.muted, fontSize: 12, hideOverlap: true },
    },
    yAxis: {
      type: "value",
      splitLine: { lineStyle: { color: colors.border } },
      axisLabel: { color: colors.muted, fontSize: 12 },
    },
  };
  const providerTotal = providers.reduce((sum, item) => sum + item.total_tokens, 0);
  return [
    {
      ...common,
      tooltip: {
        ...tooltip,
        trigger: "axis",
        formatter: (params: unknown) => {
          const item: unknown = Array.isArray(params) ? params[0] : params;
          if (
            !item ||
            typeof item !== "object" ||
            !("dataIndex" in item) ||
            typeof item.dataIndex !== "number"
          )
            return "";
          const point = points[item.dataIndex];
          return point
            ? `${point.date_full}\n分析 ${point.request_count} 次\n成功 ${point.succeeded_count} 次 · 失败 ${point.failed_count} 次`
            : "";
        },
      },
      series: [
        {
          name: "分析次数",
          type: "line",
          data: points.map((point) => point.request_count),
          showSymbol: points.length <= 14,
          symbolSize: 5,
          lineStyle: { width: 2, color: colors.accent },
          itemStyle: { color: colors.accent },
        },
      ],
    },
    {
      ...common,
      legend: { top: 0, data: ["输入", "输出"], textStyle: { color: colors.muted, fontSize: 12 } },
      tooltip: {
        ...tooltip,
        trigger: "axis",
        formatter: (params: unknown) => {
          const item: unknown = Array.isArray(params) ? params[0] : params;
          if (
            !item ||
            typeof item !== "object" ||
            !("dataIndex" in item) ||
            typeof item.dataIndex !== "number"
          )
            return "";
          const point = points[item.dataIndex];
          return point
            ? `${point.date_full}\n总消耗 ${point.total_tokens.toLocaleString()} Tokens\n输入 ${point.prompt_tokens.toLocaleString()} · 输出 ${point.completion_tokens.toLocaleString()}`
            : "";
        },
      },
      series: [
        {
          name: "输入",
          type: "bar",
          stack: "tokens",
          data: points.map((point) => point.prompt_tokens),
          itemStyle: { color: colors.accent },
        },
        {
          name: "输出",
          type: "bar",
          stack: "tokens",
          data: points.map((point) => point.completion_tokens),
          itemStyle: { color: colors.muted },
        },
      ],
    },
    {
      ...common,
      xAxis: { show: false },
      yAxis: { show: false },
      tooltip: {
        ...tooltip,
        trigger: "item",
        formatter: (item: unknown) => {
          if (
            !item ||
            typeof item !== "object" ||
            !("dataIndex" in item) ||
            typeof item.dataIndex !== "number"
          )
            return "";
          const provider = providers[item.dataIndex];
          return provider
            ? `${provider.name}\n${provider.total_tokens.toLocaleString()} Tokens${providerTotal > 0 ? ` · ${((provider.total_tokens / providerTotal) * 100).toFixed(1)}%` : ""}\n分析 ${provider.request_count} 次`
            : "";
        },
      },
      series: [
        {
          name: "服务商消耗",
          type: "pie",
          radius: ["54%", "80%"],
          center: ["50%", "50%"],
          stillShowZeroSum: false,
          label: { show: false },
          labelLine: { show: false },
          emphasis: { scale: false },
          itemStyle: { borderColor: colors.background, borderWidth: 2 },
          data: providers.map((item, index) => ({
            name: item.name,
            value: item.total_tokens,
            itemStyle: { color: colors.providerColors[index % colors.providerColors.length] },
          })),
        },
      ],
    },
  ];
}
