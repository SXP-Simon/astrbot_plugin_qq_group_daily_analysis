import type { TraceMetrics, MetricsViewMode } from "../model/traceMetrics";

export function TraceMetricsTable({
  metrics,
  mode,
}: {
  metrics: TraceMetrics;
  mode: MetricsViewMode;
}) {
  const rows =
    mode === "duration"
      ? metrics.stages.map((item) => ({
          label: item.label,
          value: item.durationMs,
          unit: "ms",
          detail:
            item.ratio !== null ? `占${item.denominator} ${item.ratio.toFixed(1)}%` : "比例未记录",
        }))
      : mode === "memory"
        ? metrics.memory.map((item) => ({
            label: item.label,
            value: item.rss,
            unit: "MiB",
            detail:
              item.delta !== null
                ? `相邻采样净变化 ${item.delta > 0 ? "+" : ""}${item.delta.toFixed(1)} MiB`
                : "",
          }))
        : metrics.dataflow.map((item) => ({
            label: item.label,
            value: item.sizeKb,
            unit: "KB",
            detail: "",
          }));
  return (
    <details className="mt-3 text-sm">
      <summary className="cursor-pointer text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring">
        查看图表数据
      </summary>
      <div className="mt-2 max-h-80 overflow-auto">
        <table className="ui-data-table w-full border-collapse text-left text-xs">
          <caption className="sr-only">
            {mode === "duration"
              ? "阶段耗时记录"
              : mode === "memory"
                ? "宿主内存采样"
                : "传输体积记录"}
          </caption>
          <thead>
            <tr>
              <th className="p-2 font-medium">记录</th>
              <th className="p-2 font-medium">数值</th>
              <th className="p-2 font-medium">对照</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, index) => (
              <tr key={index} className="border-0 border-t border-solid border-border">
                <td className="p-2">{row.label}</td>
                <td className="p-2 font-mono">
                  {row.value === null ? "未记录" : `${row.value.toLocaleString()} ${row.unit}`}
                </td>
                <td className="p-2">{row.detail}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
