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
  return (
    <section
      aria-labelledby="analysis-runtime"
      className="min-w-0 space-y-4 rounded-xl border border-border bg-card p-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="analysis-runtime" className="m-0 text-lg font-medium">
          分析运行状态
        </h2>
        <span className="text-xs text-muted-foreground">
          {error
            ? "更新失败，以下为上次读取结果"
            : runtime
              ? `读取于 ${new Date(runtime.captured_at * 1000).toLocaleTimeString("zh-CN")}`
              : "状态尚未读取"}
        </span>
      </div>
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        <dl className="m-0">
          <dt className="text-sm text-muted-foreground">平均分析耗时</dt>
          <dd className="m-0 mt-1 text-2xl tabular-nums">
            {performance?.avg_duration_ms != null
              ? formatDuration(performance.avg_duration_ms)
              : "暂无记录"}
          </dd>
          <p className="mb-0 mt-1 text-xs text-muted-foreground">
            {performance
              ? `${performance.sample_count} 次已完成分析的实际耗时`
              : "等待分析耗时数据"}
          </p>
        </dl>
        <dl className="m-0">
          <dt className="text-sm text-muted-foreground">最近一次耗时</dt>
          <dd className="m-0 mt-1 text-2xl tabular-nums">
            {performance?.latest_duration_ms != null
              ? formatDuration(performance.latest_duration_ms)
              : "暂无记录"}
          </dd>
          <p className="mb-0 mt-1 text-xs text-muted-foreground">
            完整任务耗时，含分析、渲染与发送
          </p>
        </dl>
        <dl className="col-span-2 m-0 sm:col-span-1">
          <dt className="text-sm text-muted-foreground">模型熔断</dt>
          <dd className={`m-0 mt-1 text-2xl ${cooling || recovering ? "text-warning" : ""}`}>
            {!runtime ? "未读取" : `${cooling} 冷却 · ${recovering} 待恢复`}
          </dd>
          <p className="mb-0 mt-1 text-xs text-muted-foreground">
            {runtime ? `${circuits.length} 个模型有本次运行记录` : "等待运行状态"}
          </p>
        </dl>
      </div>
      {runtime &&
        (circuits.length === 0 ? (
          <p className="m-0 text-sm text-muted-foreground">本次运行还没有模型调用记录。</p>
        ) : (
          <ul
            aria-label="模型熔断状态"
            className="m-0 max-h-64 list-none overflow-y-auto rounded-lg bg-secondary-soft px-3 py-1"
          >
            {circuits.map(([id, circuit]) => {
              const label =
                circuit.state === "OPEN"
                  ? circuit.retry_after_seconds > 0
                    ? "冷却中"
                    : "等待恢复尝试"
                  : circuit.state === "HALF_OPEN"
                    ? "恢复尝试中"
                    : circuit.failure_count > 0
                      ? "失败累积"
                      : "未熔断";
              const attention = circuit.state !== "CLOSED" || circuit.failure_count > 0;
              return (
                <li
                  key={id}
                  className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-border py-2 last:border-0"
                >
                  <span className="min-w-0 break-all text-sm">{id}</span>
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                    <span className={attention ? "text-warning" : "text-muted-foreground"}>
                      {label}
                    </span>
                    <span className="text-muted-foreground">
                      失败 {circuit.failure_count} / {circuit.failure_threshold}
                    </span>
                    {circuit.state === "OPEN" && circuit.retry_after_seconds > 0 && (
                      <span>读取时剩余 {Math.ceil(circuit.retry_after_seconds)} 秒</span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        ))}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="m-0 text-xs text-muted-foreground">
          并发强度、模型和重试策略可在配置区调整。
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => onOpenConfig("performance")}>
            并发限流设置
          </Button>
          <Button variant="outline" size="sm" onClick={() => onOpenConfig("llm")}>
            LLM 设置
          </Button>
        </div>
      </div>
      <details className="text-xs text-muted-foreground">
        <summary className="cursor-pointer">统计与恢复规则</summary>
        <p className="mb-0 leading-relaxed">
          耗时来自已保存的成功分析记录（含带警告完成），排除失败、取消、运行中与缺失耗时的记录；不是模型生成速度，也不推算理论吞吐量。熔断状态按模型共享，仅保留在本次插件进程内。冷却结束后由下一次实际请求尝试恢复，不会自动探测；刷新只读取状态。失败按调用尝试计数，包含重试；已识别的内容风控、格式参数兼容错误及主动取消不计入。熔断只覆盖分析
          LLM（含漫画分镜），不覆盖实际生图。排队请求取得槽位后会再次检查熔断；恢复时仅放行一个探测，其他请求按回退规则切换模型。已发出的请求不会强制中断。
        </p>
      </details>
    </section>
  );
}
