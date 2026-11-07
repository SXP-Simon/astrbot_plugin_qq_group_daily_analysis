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
    grid: { top: 10, bottom: 20, left: 8, right: 20, containLabel: true },
    xAxis: {
      type: "value",
      minInterval: 1,
      splitLine: { lineStyle: { color: color("--border") } },
      axisLabel: {
        color: color("--muted-foreground"),
        hideOverlap: true,
        formatter: (value: number) =>
          value >= 10000 ? `${Number((value / 10000).toFixed(1))}万` : String(value),
      },
    },
    yAxis: {
      type: "category",
      inverse: true,
      data: plotted.map((row) => row.name),
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: { color: color("--foreground"), width: 108, overflow: "truncate" },
    },
    series: [
      {
        type: "bar",
        name: "总 Tokens",
        barMaxWidth: 18,
        data: plotted.map((row) => row.total),
        itemStyle: { color: color("--ring"), borderRadius: [0, 4, 4, 0] },
      },
    ],
  };
  return (
    <section aria-label="模型消耗" className="min-w-0 space-y-4">
      <h2 className="m-0 text-lg font-medium">模型消耗</h2>
      <dl className="m-0 grid grid-cols-3 gap-3">
        {[
          ["总 Tokens", total],
          ["输入 Tokens", recordedCount(tokenUsage?.prompt_tokens)],
          ["输出 Tokens", recordedCount(tokenUsage?.completion_tokens)],
        ].map(([label, value]) => (
          <div key={label} className="min-w-0">
            <dt className="text-sm text-muted-foreground">{label}</dt>
            <dd className="m-0 mt-1 break-words text-lg tabular-nums">
              {typeof value === "number" ? value.toLocaleString() : "未记录"}
            </dd>
          </div>
        ))}
      </dl>
      {plotted.length > 0 && (
        <ReactECharts
          option={option}
          notMerge
          style={{ height: Math.min(480, Math.max(170, plotted.length * 34 + 50)), width: "100%" }}
        />
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
              <thead className="sticky top-0 bg-muted">
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
