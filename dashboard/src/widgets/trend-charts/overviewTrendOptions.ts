import type { EChartsOption } from "echarts";
import type { AnalyticsTrendPoint, ProviderBreakdownItem } from "../../entities/metric/model/types";

interface Palette {
  text: string;
  muted: string;
  border: string;
  background: string;
  accent: string;
  input?: string;
  output?: string;
  success?: string;
  danger?: string;
  providerColors: string[];
}

function tooltipText(
  content: string,
  rows: { label: string; value: string; color: string }[] = [],
): HTMLDivElement {
  const element = document.createElement("div");
  // 服务商名称可能来自用户配置，仅写入文本，避免被当成 HTML 执行。
  if (!rows.length) {
    element.textContent = content;
    return element;
  }
  element.style.display = "grid";
  element.style.gap = "6px";
  element.style.minWidth = "160px";
  const title = document.createElement("div");
  title.textContent = content;
  element.append(title);
  for (const row of rows) {
    const line = document.createElement("div");
    line.style.display = "grid";
    line.style.gridTemplateColumns = "8px minmax(0, 1fr) auto";
    line.style.columnGap = "8px";
    const marker = document.createElement("span");
    marker.setAttribute("aria-hidden", "true");
    Object.assign(marker.style, {
      width: "8px",
      height: "8px",
      borderRadius: "50%",
      alignSelf: "center",
      backgroundColor: row.color,
    });
    const label = document.createElement("span");
    label.textContent = row.label;
    const value = document.createElement("span");
    value.textContent = row.value;
    value.style.fontWeight = "500";
    value.style.fontVariantNumeric = "tabular-nums";
    line.append(marker, label, value);
    element.append(line);
  }
  return element;
}

export function createOverviewTrendOptions(
  points: AnalyticsTrendPoint[],
  providers: ProviderBreakdownItem[],
  colors: Palette,
): EChartsOption[] {
  const tooltip = {
    // SVG 内的富文本提示会挡住扇区命中；独立浮层不接收鼠标事件。
    renderMode: "html" as const,
    className: "overview-trend-tooltip",
    enterable: false,
    transitionDuration: 0,
    extraCssText:
      "pointer-events: none; white-space: pre-wrap; overflow-wrap: anywhere; max-width: 280px;",
    confine: true,
    backgroundColor: colors.background,
    borderColor: colors.border,
    textStyle: { color: colors.text, fontSize: 12 },
  };
  const common: EChartsOption = {
    animation: false,
    backgroundColor: "transparent",
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
      aria: {
        enabled: true,
        label: {
          description: `分析次数折线图，${points.length} 个时间点，共 ${points.reduce((sum, point) => sum + point.request_count, 0)} 次分析。完整数值见下方趋势明细。`,
        },
      },
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
            ? tooltipText(point.date_full, [
                { label: "分析", value: `${point.request_count} 次`, color: colors.accent },
                {
                  label: "成功",
                  value: `${point.succeeded_count} 次`,
                  color: colors.success ?? colors.accent,
                },
                {
                  label: "失败",
                  value: `${point.failed_count} 次`,
                  color: colors.danger ?? colors.accent,
                },
              ])
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
      aria: {
        enabled: true,
        label: {
          description: `模型消耗堆叠柱图，${points.length} 个时间点。输入 ${points.reduce((sum, point) => sum + point.prompt_tokens, 0).toLocaleString()} Tokens，输出 ${points.reduce((sum, point) => sum + point.completion_tokens, 0).toLocaleString()} Tokens。完整数值见下方趋势明细。`,
        },
      },
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
            ? tooltipText(point.date_full, [
                {
                  label: "总消耗",
                  value: `${point.total_tokens.toLocaleString()} Tokens`,
                  color: colors.accent,
                },
                {
                  label: "输入",
                  value: point.prompt_tokens.toLocaleString(),
                  color: colors.input ?? colors.accent,
                },
                {
                  label: "输出",
                  value: point.completion_tokens.toLocaleString(),
                  color: colors.output ?? colors.providerColors[1] ?? colors.accent,
                },
              ])
            : "";
        },
      },
      series: [
        {
          name: "输入",
          type: "bar",
          stack: "tokens",
          data: points.map((point) => point.prompt_tokens),
          itemStyle: { color: colors.input ?? colors.accent },
        },
        {
          name: "输出",
          type: "bar",
          stack: "tokens",
          data: points.map((point) => point.completion_tokens),
          itemStyle: { color: colors.output ?? colors.providerColors[1] ?? colors.accent },
        },
      ],
    },
    {
      ...common,
      aria: {
        enabled: true,
        label: {
          description: `服务商消耗环形图，图中 ${providers.length} 项，共 ${providerTotal.toLocaleString()} Tokens。图例显示占比，全部渠道见下方服务商明细。`,
        },
      },
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
          return tooltipText(
            provider
              ? `${provider.name}\n${provider.total_tokens.toLocaleString()} Tokens${providerTotal > 0 ? ` · ${((provider.total_tokens / providerTotal) * 100).toFixed(1)}%` : ""}\n分析 ${provider.request_count} 次`
              : "",
          );
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
