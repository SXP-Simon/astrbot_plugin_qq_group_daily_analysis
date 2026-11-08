import { resolveChartColor } from "../../../shared/lib/chartColors";
import { useMemo, useState } from "react";
import ReactECharts from "echarts-for-react";
import type { TraceRecord } from "../model/types";
import { getTraceMetrics, type MetricsViewMode, type PipelineMode } from "../model/traceMetrics";
import { createTraceMetricsOption } from "./traceMetricsOption";
import { TraceMetricsTable } from "./TraceMetricsTable";
import { useTheme } from "../../../shared/lib/useTheme";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "../../../shared/ui/tabs";
import { Button } from "../../../shared/ui/button";

export function TraceMetricsChart({ trace }: { trace: TraceRecord }) {
  const [mode, setMode] = useState<MetricsViewMode>("duration");
  const [pipeline, setPipeline] = useState<PipelineMode>("effective");
  useTheme();
  const metrics = useMemo(() => getTraceMetrics(trace, pipeline), [trace, pipeline]);
  const style = getComputedStyle(document.documentElement);
  const color = (name: string) => resolveChartColor(style.getPropertyValue(name), style.color);
  const option = createTraceMetricsOption(metrics, mode, {
    text: color("--foreground"),
    muted: color("--muted-foreground"),
    border: color("--border"),
    background: color("--card"),
    accent: color("--ring"),
    danger: color("--destructive"),
  });
  const hasData =
    mode === "duration"
      ? metrics.stages.length > 0
      : mode === "memory"
        ? metrics.memory.some((point) => point.rss !== null)
        : metrics.dataflow.some((point) => point.sizeKb !== null);
  const height = mode === "duration" ? Math.max(220, metrics.stages.length * 28 + 40) : 240;
  return (
    <div className="min-w-0">
      <div className="mb-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-muted-foreground">
        <span>
          记录总耗时：
          {metrics.totalDurationMs === null
            ? "未记录"
            : `${metrics.totalDurationMs.toLocaleString()} ms`}
        </span>
        <span>
          宿主采样峰值：
          {metrics.peakMemoryMb === null ? "未记录" : `${metrics.peakMemoryMb.toFixed(1)} MiB`}
        </span>
        {metrics.deltaMemoryMb !== null && (
          <span>
            宿主净变化：{metrics.deltaMemoryMb > 0 ? "+" : ""}
            {metrics.deltaMemoryMb.toFixed(1)} MiB
          </span>
        )}
      </div>
      {metrics.retryGroups.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant={pipeline === "effective" ? "secondary" : "ghost"}
            aria-pressed={pipeline === "effective"}
            onClick={() => setPipeline("effective")}
          >
            精简链路
          </Button>
          <Button
            size="sm"
            variant={pipeline === "all" ? "secondary" : "ghost"}
            aria-pressed={pipeline === "all"}
            onClick={() => setPipeline("all")}
          >
            全量重试 ({trace.spans?.length || 0})
          </Button>
          <span className="text-sm text-muted-foreground">
            {metrics.retryGroups.map((group) => `${group.label} ${group.attempts} 次`).join("、")}
          </span>
        </div>
      )}
      <Tabs
        value={mode}
        onValueChange={(value) => {
          if (value === "duration" || value === "memory" || value === "dataflow") setMode(value);
        }}
      >
        <TabsList aria-label="任务指标" className="max-w-full flex-wrap">
          <TabsTrigger value="duration">阶段耗时</TabsTrigger>
          <TabsTrigger value="memory">宿主 RSS 采样</TabsTrigger>
          <TabsTrigger value="dataflow">传输体积</TabsTrigger>
        </TabsList>
        <TabsContent value={mode}>
          <p className="my-3 text-sm text-muted-foreground">
            {mode === "duration"
              ? "父子和并行阶段不相加。顶层对照任务总耗时，子阶段对照父阶段；缺失记录不补为零。"
              : mode === "memory"
                ? "这里是宿主的阶段边界采样，不包含 Typst 子进程；空缺处表示没有记录。"
                : "只展示本次记录的文件与传输大小；没有记录不代表未生成报告。"}
          </p>
          {hasData ? (
            <div className="max-h-96 overflow-auto">
              <ReactECharts
                option={option}
                notMerge
                style={{ height, width: "100%" }}
                opts={{ renderer: "svg" }}
              />
            </div>
          ) : (
            <p className="py-8 text-center text-sm text-muted-foreground">没有对应的采样记录</p>
          )}
          <TraceMetricsTable metrics={metrics} mode={mode} />
        </TabsContent>
      </Tabs>
    </div>
  );
}
