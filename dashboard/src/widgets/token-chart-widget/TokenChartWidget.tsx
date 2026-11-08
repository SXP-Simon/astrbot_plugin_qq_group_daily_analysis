import ReactECharts from "echarts-for-react";
import type { EChartsOption } from "echarts";
import type { TokenUsage } from "../../entities/trace/model/types";
import { useTheme } from "../../shared/lib/useTheme";

interface TokenChartWidgetProps {
  tokenUsage?: TokenUsage | null;
  totalTokens?: number | null;
}

const analyzerLabels: Record<string, string> = {
  topics: "话题分析",
  user_titles: "群友画像",
  golden_quotes: "群聊金句",
  chat_quality: "群聊质量",
  comic_storyboard: "漫画分镜",
};
const recordedCount = (value: number | null | undefined) =>
  typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;

export function TokenChartWidget({ tokenUsage, totalTokens }: TokenChartWidgetProps) {
  useTheme();
  const style = getComputedStyle(document.documentElement);
  const color = (name: string) => style.getPropertyValue(name).trim() || "currentColor";
  const total = recordedCount(tokenUsage?.total_tokens ?? totalTokens);
  const rows = Object.entries(tokenUsage?.per_analyzer ?? {})
    .map(([id, usage]) => ({
      id,
      name: analyzerLabels[id] || id,
      input: recordedCount(usage.prompt_tokens),
      output: recordedCount(usage.completion_tokens),
      total: recordedCount(usage.total_tokens),
    }))
    .sort((a, b) => (b.total ?? -1) - (a.total ?? -1));
  const plotted = rows.filter((row) => row.total !== null && row.total > 0);
  const canStack = plotted.every(
    (row) => row.input !== null && row.output !== null && row.input + row.output === row.total,
  );
  const moduleTotal = rows.reduce((sum, row) => sum + (row.total ?? 0), 0);
  const mismatched =
    rows.length > 0 &&
    rows.every((row) => row.total !== null) &&
    total !== null &&
    moduleTotal !== total;
  const option: EChartsOption = {
    animation: false,
    backgroundColor: "transparent",
    textStyle: { fontFamily: '"LXGW WenKai Screen", sans-serif', color: color("--foreground") },
    tooltip: {
      trigger: "axis",
      renderMode: "richText",
      confine: true,
      backgroundColor: color("--card"),
      borderColor: color("--border"),
      textStyle: { color: color("--foreground") },
    },
    grid: { top: 4, bottom: 4, left: 0, right: 64, containLabel: true },
    xAxis: {
      type: "value",
      show: false,
      max: "dataMax",
      minInterval: 1,
    },
    yAxis: {
      type: "category",
      inverse: true,
      data: plotted.map((row) => row.name),
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: {
        color: color("--foreground"),
        fontSize: 12,
        width: 96,
        overflow: "truncate",
        margin: 12,
      },
    },
    series: [
      {
        type: "bar",
        name: canStack ? "输入 Tokens" : "总 Tokens",
        stack: "usage",
        barWidth: 10,
        showBackground: true,
        backgroundStyle: { color: color("--muted"), borderRadius: 5 },
        data: plotted.map((row) => (canStack ? row.input : row.total)),
        itemStyle: { color: color("--chart-input"), borderRadius: canStack ? [5, 0, 0, 5] : 5 },
        label: {
          show: !canStack,
          position: "right",
          distance: 10,
          color: color("--foreground"),
          formatter: (params) => plotted[params.dataIndex].total!.toLocaleString(),
        },
      },
      ...(canStack
        ? [
            {
              type: "bar" as const,
              name: "输出 Tokens",
              stack: "usage",
              barWidth: 10,
              data: plotted.map((row) => row.output),
              itemStyle: { color: color("--chart-output"), borderRadius: [0, 5, 5, 0] },
              label: {
                show: true,
                position: "right" as const,
                distance: 10,
                color: color("--foreground"),
                formatter: (params: { dataIndex: number }) =>
                  plotted[params.dataIndex].total!.toLocaleString(),
              },
            },
          ]
        : []),
    ],
  };
  return (
    <section aria-label="模型消耗" className="min-w-0 space-y-4">
      <h2 className="m-0 text-lg font-medium">模型消耗</h2>
      <dl className="m-0 grid grid-cols-3 gap-2">
        {[
          { label: "总 Tokens", value: total, tone: "bg-card" },
          {
            label: "输入 Tokens",
            value: recordedCount(tokenUsage?.prompt_tokens),
            tone: "bg-primary-soft",
          },
          {
            label: "输出 Tokens",
            value: recordedCount(tokenUsage?.completion_tokens),
            tone: "bg-secondary-soft",
          },
        ].map(({ label, value, tone }) => (
          <div key={label} className={`min-w-0 rounded-xl p-3 ${tone}`}>
            <dt className="text-sm text-muted-foreground">{label}</dt>
            <dd className="m-0 mt-1 break-words text-lg tabular-nums">
              {typeof value === "number" ? value.toLocaleString() : "未记录"}
            </dd>
          </div>
        ))}
      </dl>
      {plotted.length > 0 && (
        <div className="min-w-0 overflow-hidden">
          <div
            aria-label="图例"
            className="mb-1 flex justify-end gap-4 text-xs text-muted-foreground"
          >
            <span className="inline-flex items-center gap-1.5">
              <span
                aria-hidden="true"
                className="size-2 rounded-sm"
                style={{ background: color("--chart-input") }}
              />
              {canStack ? "输入" : "模块总量"}
            </span>
            {canStack && (
              <span className="inline-flex items-center gap-1.5">
                <span
                  aria-hidden="true"
                  className="size-2 rounded-sm"
                  style={{ background: color("--chart-output") }}
                />
                输出
              </span>
            )}
          </div>
          <ReactECharts
            option={option}
            notMerge
            style={{ height: Math.min(480, Math.max(94, plotted.length * 42 + 8)), width: "100%" }}
          />
        </div>
      )}
      {rows.length ? (
        <>
          {mismatched && (
            <p role="status" className="m-0 text-sm text-muted-foreground">
              模块记录合计 {moduleTotal.toLocaleString()} Tokens，与任务总数不同，以下保留原始记录。
            </p>
          )}
          <div
            role="region"
            aria-label="模块消耗明细"
            tabIndex={0}
            className="max-h-80 overflow-auto rounded-xl border border-solid border-border focus-visible:outline-2 focus-visible:outline-ring"
          >
            <table className="w-full border-collapse text-sm">
              <caption className="sr-only">各模块模型消耗，单位 Tokens</caption>
              <thead className="sticky top-0 bg-secondary">
                <tr>
                  {["分析模块", "输入", "输出", "合计"].map((label) => (
                    <th key={label} scope="col" className="px-3 py-2 text-left font-medium">
                      {label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-0 border-t border-solid border-border">
                    <th
                      scope="row"
                      className="max-w-64 break-words px-3 py-2 text-left font-normal"
                    >
                      {row.name}
                    </th>
                    {[row.input, row.output, row.total].map((value, index) => (
                      <td key={index} className="px-3 py-2 tabular-nums">
                        {value === null ? "未记录" : value.toLocaleString()}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : (
        <p role="status" className="m-0 py-6 text-sm text-muted-foreground">
          {total === null
            ? "未记录模型用量。"
            : total === 0
              ? "已记录总消耗为 0 Tokens，未保存模块明细。"
              : "仅记录了任务总用量，未保存模块明细。"}
        </p>
      )}
    </section>
  );
}
