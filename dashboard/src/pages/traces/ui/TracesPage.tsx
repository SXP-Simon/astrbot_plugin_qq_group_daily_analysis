import React from "react";
import { TraceFilterBar } from "../../../features/filter-traces/ui/TraceFilterBar";
import { TraceTable } from "../../../widgets/trace-table/TraceTable";
import { useTracesViewModel } from "../model/useTracesViewModel";

interface TracesPageProps {
  viewModel: ReturnType<typeof useTracesViewModel>;
  onViewTrace: (traceId: string) => void;
}

export const TracesPage: React.FC<TracesPageProps> = ({ viewModel, onViewTrace }) => {
  const {
    traces,
    total,
    loading,
    page,
    pageSize,
    search,
    setSearch,
    statusFilter,
    setStatusFilter,
    triggerTypeFilter,
    setTriggerTypeFilter,
    selectedGroup,
    setSelectedGroup,
    setDateRange,
    groups,
    dateRange,
    sortField,
    sortOrder,
    changePage,
    changeSort,
    resetFilters,
    error,
    groupsError,
    refresh,
  } = viewModel;

  return (
    <section className="space-y-5" aria-label="分析记录">
      {/* 过滤筛选工具栏 (Feature Molecule) */}
      <TraceFilterBar
        search={search}
        selectedGroup={selectedGroup}
        statusFilter={statusFilter}
        triggerTypeFilter={triggerTypeFilter}
        groups={groups}
        dateRange={dateRange}
        loading={loading}
        onSearchChange={setSearch}
        onGroupChange={setSelectedGroup}
        onStatusChange={setStatusFilter}
        onTriggerTypeChange={setTriggerTypeFilter}
        onDateRangeChange={setDateRange}
        onReset={resetFilters}
        onRefresh={() => refresh(false)}
      />
      {viewModel.hasUpdates && (
        <p role="status" className="text-sm text-info">
          分析记录有更新，点击“刷新”查看。当前页保持不变。
        </p>
      )}
      {groupsError && (
        <p role="alert" className="text-sm text-destructive">
          {groupsError}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
          {traces.length > 0 && " 下方保留上一次加载的记录。"}
        </p>
      )}

      {/* 紧凑数据表格 (Widget Organism) */}
      <TraceTable
        traces={traces}
        total={total}
        loading={loading}
        page={page}
        pageSize={pageSize}
        onViewTrace={onViewTrace}
        sortField={sortField}
        sortOrder={sortOrder}
        onPageChange={changePage}
        onSortChange={changeSort}
      />
    </section>
  );
};
