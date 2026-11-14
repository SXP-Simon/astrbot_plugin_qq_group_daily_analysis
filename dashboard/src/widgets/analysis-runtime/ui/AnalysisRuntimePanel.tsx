import type { MetricsSummary } from "@/entities/metric/model/types";
import { Button } from "@/shared/ui/button";
import { formatDuration } from "@/shared/lib/formatters";

export function AnalysisRuntimePanel({
  metrics,
  error,
  onOpenConfig,
}: {
  metrics: MetricsSummary | null;
  error: string;
  onOpenConfig: (category: "performance" | "llm") => void;
}) {
  const runtime = metrics?.llm_runtime;
  const performance = metrics?.analysis_performance;
  const circuits = Object.entries(runtime?.circuits ?? {});
  const cooling = circuits.filter(
    ([, circuit]) => circuit.state === "OPEN" && circuit.retry_after_seconds > 0,
  ).length;
  const recovering = circuits.filter(
    ([, circuit]) =>
      circuit.state === "HALF_OPEN" ||
      (circuit.state === "OPEN" && circuit.retry_after_seconds === 0),
  ).length;
  const durationMetrics = [
    { label: "平均分析耗时", value: performance?.avg_duration_ms },
    { label: "最近一次耗时", value: performance?.latest_duration_ms },
  ];

  return (
    <section
      aria-labelledby="analysis-runtime"
      className="@container min-w-0 border-t border-border pt-6 sm:pt-7"
    >
      <header className="mb-6 flex flex-wrap items-center justify-between gap-x-6 gap-y-2">
        <h2 id="analysis-runtime" className="m-0 text-lg font-medium">
          分析运行状态
        </h2>
        <span
          className={error ? "text-sm text-warning" : "text-sm tabular-nums text-muted-foreground"}
        >
          {error
            ? runtime || performance
              ? "更新失败，以下为上次读取结果"
              : "读取失败，请刷新重试"
            : runtime
              ? `读取于 ${new Date(runtime.captured_at * 1000).toLocaleTimeString("zh-CN")}`
              : "状态尚未读取"}
        </span>
      </header>

      <div className="grid gap-7 @[52rem]:grid-cols-[minmax(0,2fr)_minmax(0,3fr)] @[52rem]:gap-10">
        <div className="min-w-0">
          <h3 className="m-0 text-base font-medium">任务耗时</h3>
          <p className="mb-0 mt-1 text-sm text-muted-foreground">
            完整任务耗时，含分析、渲染与发送
          </p>
          <dl className="mb-0 mt-5 grid grid-cols-2 gap-3 sm:gap-5">
            {durationMetrics.map(({ label, value }) => (
              <div key={label} className="min-w-0">
                <dt className="text-sm text-muted-foreground">{label}</dt>
                <dd className="m-0 mt-2 break-words text-[clamp(1.5rem,5cqw,2.5rem)] font-semibold leading-none tracking-tight tabular-nums">
                  {value != null ? formatDuration(value) : "暂无记录"}
                </dd>
              </div>
            ))}
          </dl>
          <p className="mb-0 mt-4 text-sm text-muted-foreground">
            {performance
              ? `${performance.sample_count} 次已完成分析的实际耗时`
              : "等待分析耗时数据"}
          </p>
        </div>

        <div className="@container/models min-w-0 border-t border-border pt-5 @[52rem]:border-l @[52rem]:border-t-0 @[52rem]:pl-8 @[52rem]:pt-0">
          <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <h3 className="m-0 text-base font-medium">模型熔断</h3>
            <span
              className={
                cooling || recovering
                  ? "text-sm font-medium text-warning"
                  : "text-sm text-muted-foreground"
              }
            >
              {!runtime ? "未读取" : `${cooling} 冷却 · ${recovering} 待恢复`}
            </span>
          </div>

          {runtime &&
            (circuits.length === 0 ? (
              <p className="m-0 py-3 text-sm text-muted-foreground">本次运行还没有模型调用记录。</p>
            ) : (
              <div>
                <div
                  aria-hidden="true"
                  className="hidden grid-cols-[minmax(0,1fr)_7rem_4.5rem_5rem] gap-x-3 border-b border-border pb-2.5 text-xs text-muted-foreground @[29rem]/models:grid"
                >
                  <span>模型</span>
                  <span>状态</span>
                  <span className="whitespace-nowrap">失败 / 阈值</span>
                  <span className="text-right">剩余冷却</span>
                </div>
                <ul
                  aria-label="模型熔断状态"
                  className="m-0 max-h-64 list-none divide-y divide-border overflow-y-auto p-0"
                >
                  {circuits.map(([id, circuit]) => {
                    const isCooling = circuit.state === "OPEN" && circuit.retry_after_seconds > 0;
                    let label = "未熔断";
                    if (isCooling) label = "冷却中";
                    else if (circuit.state === "OPEN") label = "等待恢复尝试";
                    else if (circuit.state === "HALF_OPEN") label = "恢复尝试中";
                    else if (circuit.failure_count > 0) label = "失败累积";
                    const attention = label !== "未熔断";
                    return (
                      <li
                        key={id}
                        className="grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-2 py-3 @[29rem]/models:grid-cols-[minmax(0,1fr)_7rem_4.5rem_5rem]"
                      >
                        <span className="min-w-0 break-all text-sm font-medium">{id}</span>
                        <span
                          className={`w-fit whitespace-nowrap rounded-full px-2.5 py-1 text-xs font-medium ${attention ? "bg-warning/12 text-warning" : "bg-success/10 text-success"}`}
                        >
                          {label}
                        </span>
                        <span className="text-xs tabular-nums text-muted-foreground">
                          <span className="@[29rem]/models:sr-only">失败 </span>
                          {circuit.failure_count} / {circuit.failure_threshold}
                        </span>
                        {isCooling ? (
                          <span className="text-right text-xs font-medium tabular-nums text-warning">
                            <span className="@[29rem]/models:sr-only">读取时剩余 </span>
                            {Math.ceil(circuit.retry_after_seconds)} 秒
                          </span>
                        ) : (
                          <span
                            aria-hidden="true"
                            className="hidden text-right text-xs text-muted-foreground @[29rem]/models:block"
                          >
                            —
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
        </div>
      </div>

      <footer className="mt-4 flex flex-wrap items-start justify-between gap-x-6 gap-y-2 border-t border-border pt-3">
        <details className="min-w-0 flex-1 basis-52 text-sm text-muted-foreground">
          <summary className="w-fit cursor-pointer rounded-md py-2 hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring">
            统计与恢复规则
          </summary>
          <p className="mb-0 mt-2 max-w-prose leading-relaxed">
            耗时来自已完成的成功分析记录，含带警告完成。熔断按模型共享，包含重试在内的失败按调用次数累计，内容风控、格式兼容错误与主动取消不计入。剩余冷却时间以读取时为准。排队请求取得槽位后会复查状态，冷却到期后只放行一个实际请求探测恢复。熔断只覆盖分析
            LLM（含漫画分镜），不覆盖实际生图。
          </p>
        </details>
        <div className="flex flex-wrap gap-2">
          <Button variant="ghost" onClick={() => onOpenConfig("performance")}>
            并发限流设置
          </Button>
          <Button variant="ghost" onClick={() => onOpenConfig("llm")}>
            LLM 设置
          </Button>
        </div>
      </footer>
    </section>
  );
}
