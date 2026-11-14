import { AnalysisRuntimePanel } from "@/widgets/analysis-runtime/ui/AnalysisRuntimePanel";
import { LoadingState } from "@/shared/ui/loading-state";
import { ActiveTaskBoard } from "@/widgets/active-task-board/ActiveTaskBoard";
import { OverviewTrendCharts } from "@/widgets/trend-charts/OverviewTrendCharts";
import { Button } from "@/shared/ui/button";
import { StatusTag } from "@/shared/ui/StatusTag";
import { formatSmartTokens, formatTimestamp } from "@/shared/lib/formatters";
import type { useOverviewViewModel } from "@/pages/overview/model/useOverviewViewModel";

interface OverviewPageProps {
  viewModel: ReturnType<typeof useOverviewViewModel>;
  onOpenConfig: (category: "performance" | "llm") => void;
  onOpenTrigger: () => void;
  onViewTrace: (traceId: string) => void;
}

export function OverviewPage({
  viewModel,
  onOpenTrigger,
  onViewTrace,
  onOpenConfig,
}: OverviewPageProps) {
  const {
    metrics,
    activeTasks,
    attentionTraces,
    loading,
    tasksLoaded,
    errors,
    feedback,
    handleCancelTask,
    acknowledgedCount,
    showAcknowledged,
    setShowAcknowledged,
    acknowledgingIds,
    acknowledgementError,
    handleAcknowledge,
  } = viewModel;
  const summaries = [
    ["今日分析", metrics?.today_traces, "次"],
    ["今日群聊", metrics?.today_active_groups, "个"],
    ["历史运行", metrics?.total_traces, "次"],
    ["成功率", metrics?.success_rate, "%"],
  ];
  return (
    <div className="space-y-8">
      {feedback && (
        <p role="status" className="m-0 text-sm">
          {feedback}
        </p>
      )}
      <section aria-labelledby="overview-metrics" className="min-w-0">
        <h2 id="overview-metrics" className="m-0 mb-4 text-lg font-medium">
          分析统计
        </h2>
        {errors.metrics && (
          <p role="alert" className="text-sm text-destructive">
            {errors.metrics}
          </p>
        )}
        <div className="grid grid-cols-2 items-start gap-x-6 gap-y-5 sm:grid-cols-3">
          {summaries.map(([label, value, unit]) => (
            <dl key={label} className="m-0">
              <dt className="text-sm text-muted-foreground">{label}</dt>
              <dd className="m-0 mt-1 text-xl tabular-nums">
                {value ?? "未读取"}
                {value !== undefined && (
                  <span className="ml-1 text-xs text-muted-foreground">{unit}</span>
                )}
              </dd>
            </dl>
          ))}
          <dl
            role="group"
            aria-label="模型消耗"
            className="m-0 flex flex-wrap gap-x-4 gap-y-2 rounded-xl bg-secondary-soft px-3 py-2"
          >
            {[
              ["今日模型消耗", metrics?.today_tokens_spent],
              ["近30天模型消耗", metrics?.total_tokens_spent],
            ].map(([label, value]) => (
              <div key={label} className="min-w-0 flex-1 basis-24">
                <dt className="text-sm text-muted-foreground">{label}</dt>
                <dd className="m-0 mt-1 flex flex-wrap items-baseline gap-x-1 text-lg tabular-nums">
                  {typeof value === "number" ? formatSmartTokens(value) : "未读取"}
                  {typeof value === "number" && (
                    <span className="text-xs text-muted-foreground">Tokens</span>
                  )}
                </dd>
              </div>
            ))}
          </dl>
        </div>
      </section>
      <AnalysisRuntimePanel metrics={metrics} error={errors.metrics} onOpenConfig={onOpenConfig} />
      {metrics && (
        <OverviewTrendCharts
          initialTrends={metrics.trends}
          totalTraces={metrics.total_traces}
          totalTokens={metrics.total_tokens_spent}
        />
      )}
      <div className="grid min-w-0 items-start gap-8 border-0 border-t border-solid border-border pt-6 xl:grid-cols-[minmax(0,1.7fr)_minmax(280px,1fr)]">
        <div className="min-w-0" aria-busy={loading}>
          {errors.tasks && (
            <p role="alert" className="mb-3 text-sm text-destructive">
              {errors.tasks}
            </p>
          )}
          {!tasksLoaded && activeTasks.length === 0 ? (
            <section aria-label="运行中任务" className="space-y-3">
              <h2 className="m-0 text-lg font-medium">正在执行中的分析任务</h2>
              {loading ? (
                <LoadingState skeleton>正在读取任务…</LoadingState>
              ) : (
                <p role="status" className="text-sm text-muted-foreground">
                  暂时无法确认运行中任务。
                </p>
              )}
              <Button variant="outline" size="sm" onClick={() => void viewModel.refresh(false)}>
                重新加载
              </Button>
            </section>
          ) : (
            <ActiveTaskBoard
              tasks={activeTasks}
              onCancelTask={handleCancelTask}
              onViewTrace={onViewTrace}
              onOpenTrigger={onOpenTrigger}
            />
          )}
        </div>
        <section
          aria-labelledby="overview-attention"
          className="min-w-0 rounded-xl bg-muted/50 p-4"
        >
          <h2 id="overview-attention" className="m-0 text-lg font-medium">
            需要关注
          </h2>
          <p className="mb-2 mt-1 text-xs text-muted-foreground">最近 20 条分析中的失败或警告</p>
          {acknowledgedCount > 0 && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setShowAcknowledged(!showAcknowledged)}
              aria-pressed={showAcknowledged}
            >
              {showAcknowledged ? "收起已知晓" : `显示已知晓（${acknowledgedCount}）`}
            </Button>
          )}
          {acknowledgementError && (
            <p role="alert" className="text-sm text-destructive">
              {acknowledgementError}
            </p>
          )}
          {errors.recent && (
            <p role="alert" className="text-sm text-destructive">
              {errors.recent}
            </p>
          )}
          {attentionTraces.length === 0 ? (
            loading ? (
              <LoadingState skeleton className="my-5">
                正在读取记录…
              </LoadingState>
            ) : (
              <p className="my-5 text-sm text-muted-foreground">
                {errors.recent
                  ? "暂时无法确认近期结果。"
                  : acknowledgedCount > 0
                    ? "这些提醒均已知晓"
                    : "近期记录中没有失败或警告"}
              </p>
            )
          ) : (
            <ul className="m-0 max-h-[560px] list-none overflow-y-auto p-0">
              {attentionTraces.map((trace) => (
                <li
                  key={trace.trace_id}
                  className="space-y-2 border-0 border-b border-solid border-border py-4 last:border-b-0"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="min-w-0 break-words text-base">
                      {trace.group_name || trace.group_id}
                    </span>
                    <StatusTag status={trace.status === "failed" ? "failed" : "warning"} />
                  </div>
                  <label className="inline-flex cursor-pointer items-center gap-2 text-xs text-muted-foreground">
                    <input
                      type="checkbox"
                      className="size-4 accent-primary"
                      aria-label={`已知晓：${trace.group_name || trace.group_id}（${trace.trace_id}）`}
                      checked={(trace.acknowledged_at ?? 0) > 0}
                      disabled={acknowledgingIds.includes(trace.trace_id)}
                      onChange={(event) =>
                        void handleAcknowledge(trace.trace_id, event.currentTarget.checked)
                      }
                    />
                    已知晓
                  </label>
                  <p className="m-0 break-all font-mono text-xs text-muted-foreground">
                    {trace.platform} · {trace.group_id}
                  </p>
                  {trace.error_message && (
                    <p className="m-0 line-clamp-3 break-words text-sm">{trace.error_message}</p>
                  )}
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <time className="text-xs text-muted-foreground">
                      {formatTimestamp(trace.started_at)}
                    </time>
                    <Button size="sm" variant="outline" onClick={() => onViewTrace(trace.trace_id)}>
                      查看过程
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </div>
  );
}
