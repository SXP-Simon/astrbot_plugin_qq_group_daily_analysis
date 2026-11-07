import { IconArrowUpRight } from "@tabler/icons-react";
import { Button } from "../../../shared/ui/button";
import { SearchSelect } from "../../../shared/ui/search-select";
import { StatusTag } from "../../../shared/ui/StatusTag";
import { ContextFunnelWidget } from "../../../widgets/context-funnel-widget/ContextFunnelWidget";
import { TokenChartWidget } from "../../../widgets/token-chart-widget/TokenChartWidget";
import { TraceFilterBar } from "../../../features/filter-traces/ui/TraceFilterBar";
import { AnalysisTimelinePicker } from "../../../widgets/timeline-picker/AnalysisTimelinePicker";
import { formatTimestamp } from "../../../shared/lib/formatters";
import type { useContextInsightViewModel } from "../model/useContextInsightViewModel";

interface ContextInsightPageProps {
  viewModel: ReturnType<typeof useContextInsightViewModel>;
  onViewTrace?: (traceId: string) => void;
}

export function ContextInsightPage({ viewModel: vm, onViewTrace }: ContextInsightPageProps) {
  return (
    <div className="space-y-6">
      <TraceFilterBar
        search={vm.search}
        selectedGroup={vm.selectedGroup}
        statusFilter={vm.statusFilter}
        dateRange={vm.dateRange}
        groups={vm.groups}
        loading={vm.loading}
        onSearchChange={vm.setSearch}
        onGroupChange={vm.setSelectedGroup}
        onStatusChange={vm.setStatusFilter}
        onDateRangeChange={vm.setDateRange}
        onReset={vm.resetFilters}
        onRefresh={() => vm.refresh(false)}
      />
      {vm.groupsError && (
        <p role="alert" className="m-0 text-sm text-destructive">
          {vm.groupsError}
        </p>
      )}
      {vm.error && (
        <p role="alert" className="m-0 text-sm text-destructive">
          {vm.error}
          {vm.traces.length > 0 && " 当前保留上次读取的记录。"}
        </p>
      )}
      <section aria-label="选择分析记录" className="space-y-3 border-t border-border pt-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 className="m-0 text-lg font-medium">选择分析记录</h2>
          <span className="text-sm text-muted-foreground">
            {vm.total > vm.traces.length
              ? `已载入最近 ${vm.traces.length} / ${vm.total} 条，可缩小筛选范围`
              : `共 ${vm.total} 条`}
          </span>
        </div>
        <SearchSelect
          label="选择分析记录"
          value={vm.selectedTrace?.trace_id ?? ""}
          disabled={vm.traces.length === 0}
          options={vm.traces.map((trace) => ({
            value: trace.trace_id,
            label: `${trace.group_name || trace.group_id} · ${trace.platform} · ${formatTimestamp(trace.started_at)} · ${trace.trace_id}`,
          }))}
          onChange={(id) =>
            vm.setSelectedTrace(vm.traces.find((trace) => trace.trace_id === id) ?? null)
          }
        />
      </section>
      {vm.loading && (
        <p role="status" className="m-0 text-sm text-muted-foreground">
          正在读取分析记录…
        </p>
      )}
      {vm.traces.length > 0 && (
        <AnalysisTimelinePicker
          traces={vm.traces}
          selectedTrace={vm.selectedTrace}
          onSelectTrace={vm.setSelectedTrace}
        />
      )}
      {vm.selectedTrace ? (
        <section
          aria-label="所选任务统计"
          className="space-y-5 border-t border-border pt-5"
          aria-busy={vm.detailLoading}
        >
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 space-y-2">
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="m-0 text-lg font-medium">
                  {vm.selectedTrace.group_name || vm.selectedTrace.group_id}
                </h2>
                <StatusTag status={vm.selectedTrace.status} />
              </div>
              <p className="m-0 break-words text-sm text-muted-foreground">
                {vm.selectedTrace.platform} · {vm.selectedTrace.group_id} ·{" "}
                {formatTimestamp(vm.selectedTrace.started_at)}
              </p>
              <p className="m-0 break-all font-mono text-xs text-muted-foreground">
                {vm.selectedTrace.trace_id}
              </p>
            </div>
            {onViewTrace && (
              <Button
                variant="outline"
                onClick={() => vm.selectedTrace && onViewTrace(vm.selectedTrace.trace_id)}
              >
                查看任务详情
                <IconArrowUpRight aria-hidden="true" />
              </Button>
            )}
          </div>
          {vm.detailLoading && (
            <p role="status" className="m-0 text-sm text-muted-foreground">
              正在读取这项任务的明细…
            </p>
          )}
          {vm.detailError && (
            <p role="alert" className="m-0 text-sm text-destructive">
              {vm.detailError}
            </p>
          )}
          <div className="grid min-w-0 grid-cols-1 gap-8 lg:grid-cols-[minmax(0,2fr)_minmax(0,3fr)]">
            <ContextFunnelWidget metrics={vm.contextMetrics} />
            <TokenChartWidget
              tokenUsage={vm.tokenUsage}
              totalTokens={vm.selectedTrace.total_tokens}
            />
          </div>
        </section>
      ) : !vm.loading && !vm.error ? (
        <p role="status" className="py-12 text-center text-muted-foreground">
          暂无符合条件的分析记录，可调整筛选或发起分析。
        </p>
      ) : null}
    </div>
  );
}
