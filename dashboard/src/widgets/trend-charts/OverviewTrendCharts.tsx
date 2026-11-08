import { memo } from "react";
import ReactECharts from "echarts-for-react";
import type { AnalyticsTrendsResponse } from "../../entities/metric/model/types";
import { formatSmartTokens } from "../../shared/lib/formatters";
import { useTheme } from "../../shared/lib/useTheme";
import { Button } from "../../shared/ui/button";
import { NativeSelect } from "../../shared/ui/native-select";
import { TREND_RANGES, useOverviewTrends } from "./model/useOverviewTrends";
import { createOverviewTrendOptions } from "./overviewTrendOptions";
import { TrendDataTables } from "./TrendDataTables";

interface OverviewTrendChartsProps {
  initialTrends?: AnalyticsTrendsResponse;
  totalTraces?: number;
  totalTokens?: number;
}

// 运行中任务每秒刷新耗时；相同趋势数据不应重设图表并打断悬浮提示。
export const OverviewTrendCharts = memo(function OverviewTrendCharts({
  initialTrends,
}: OverviewTrendChartsProps) {
  const vm = useOverviewTrends(initialTrends);
  useTheme();
  const style = getComputedStyle(document.documentElement);
  const color = (name: string) => style.getPropertyValue(name).trim() || "currentColor";
  const providerColors = [
    "--ring",
    "--info",
    "--creative",
    "--warning",
    "--success",
    "--chart-output",
    "--muted-foreground",
  ].map(color);
  const providerTotal = vm.providers.reduce((sum, item) => sum + item.total_tokens, 0);
  const options = createOverviewTrendOptions(vm.points, vm.providerChart, {
    text: color("--foreground"),
    muted: color("--muted-foreground"),
    border: color("--border"),
    background: color("--card"),
    accent: color("--ring"),
    input: style.getPropertyValue("--chart-trend-input").trim() || undefined,
    output: style.getPropertyValue("--chart-trend-output").trim() || undefined,
    providerColors,
  });
  const selectedLabel = TREND_RANGES.find((item) => item.value === vm.range)!.label;
  const displayedLabel = TREND_RANGES.find((item) => item.value === vm.displayedRange)?.label;
  const charts = [
    { label: "分析次数", value: `${vm.totalRequests} 次`, hasData: vm.points.length > 0 },
    {
      label: "模型消耗",
      value: `${formatSmartTokens(vm.totalTokens)} Tokens`,
      hasData: vm.points.length > 0,
    },
    {
      label: "服务商消耗占比",
      value: `${vm.providers.length} 个渠道`,
      hasData: vm.providers.length > 0,
    },
  ];
  return (
    <section aria-labelledby="overview-trends" className="min-w-0" aria-busy={vm.loading}>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <h2 id="overview-trends" className="m-0 text-lg font-medium">
          分析趋势
        </h2>
        <div className="flex items-center gap-2">
          <div className="w-36">
            <NativeSelect
              aria-label="趋势时间范围"
              value={vm.range}
              onChange={(event) => vm.selectRange(event.target.value)}
            >
              {TREND_RANGES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </NativeSelect>
          </div>
          <Button variant="outline" size="sm" disabled={vm.loading} onClick={vm.refresh}>
            刷新趋势
          </Button>
        </div>
      </div>
      {vm.loading && (
        <p role="status" className="text-sm text-muted-foreground">
          正在读取{selectedLabel}…
        </p>
      )}
      {vm.error && (
        <p role="alert" className="text-sm text-destructive">
          {vm.error}
        </p>
      )}
      {displayedLabel && (vm.error || vm.range !== vm.displayedRange) && (
        <p className="text-sm text-muted-foreground">当前保留的是{displayedLabel}的数据。</p>
      )}
      <div className="grid min-w-0 gap-6 lg:grid-cols-3">
        {charts.map((chart, index) => (
          <section
            key={chart.label}
            aria-label={chart.label}
            className="min-w-0 rounded-xl bg-muted/40 p-3"
          >
            <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
              <h3 className="m-0 text-base font-medium">{chart.label}</h3>
              <span className="text-sm tabular-nums text-muted-foreground">
                {vm.displayedRange ? chart.value : "未读取"}
              </span>
            </div>
            {chart.hasData && index === 2 ? (
              <div className="grid min-h-[230px] grid-cols-[minmax(0,0.9fr)_minmax(0,1fr)] items-center gap-3">
                {providerTotal > 0 ? (
                  <ReactECharts
                    option={options[index]}
                    notMerge
                    style={{ height: 200, width: "100%" }}
                    opts={{ renderer: "svg" }}
                  />
                ) : (
                  <p className="text-center text-sm text-muted-foreground">暂无消耗记录</p>
                )}
                <ul
                  aria-label="服务商占比图例"
                  className="m-0 grid max-h-[230px] list-none gap-2 overflow-y-auto p-0"
                >
                  {vm.providerChart.map((provider, providerIndex) => (
                    <li
                      key={`${provider.name}-${providerIndex}`}
                      className="flex min-w-0 items-center gap-2 text-xs"
                    >
                      <span
                        aria-hidden="true"
                        className="size-2 shrink-0 rounded-sm"
                        style={{ backgroundColor: providerColors[providerIndex] }}
                      />
                      <span
                        className="min-w-0 flex-1 truncate"
                        title={`${provider.name} · ${provider.total_tokens.toLocaleString()} Tokens · 分析 ${provider.request_count} 次`}
                      >
                        {provider.name}
                      </span>
                      <span className="shrink-0 tabular-nums text-muted-foreground">
                        {providerTotal > 0
                          ? `${((provider.total_tokens / providerTotal) * 100).toFixed(1)}%`
                          : "—"}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            ) : chart.hasData ? (
              <ReactECharts
                option={options[index]}
                notMerge
                style={{ height: 230, width: "100%" }}
                opts={{ renderer: "svg" }}
              />
            ) : (
              <p className="flex min-h-40 items-center justify-center text-sm text-muted-foreground">
                {vm.displayedRange ? "此范围暂无记录" : "暂无可显示的数据"}
              </p>
            )}
          </section>
        ))}
      </div>
      {vm.displayedRange && (
        <TrendDataTables points={vm.points} providers={vm.providers} rangeLabel={displayedLabel!} />
      )}
    </section>
  );
});
