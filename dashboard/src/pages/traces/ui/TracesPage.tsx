import React from "react";
import { Card } from "antd";
import { TraceFilterBar } from "../../../features/filter-traces/ui/TraceFilterBar";
import { TraceTable } from "../../../widgets/trace-table/TraceTable";
import { useTracesViewModel } from "../model/useTracesViewModel";

interface TracesPageProps {
  viewModel: ReturnType<typeof useTracesViewModel>;
  onViewTrace: (traceId: string) => void;
}

export const TracesPage: React.FC<TracesPageProps> = ({
  viewModel,
  onViewTrace,
}) => {
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
    selectedGroup,
    setSelectedGroup,
    setDateRange,
    groups,
    handleTableChange,
    refresh,
  } = viewModel;

  return (
    <Card size="small">
      {/* 过滤筛选工具栏 (Feature Molecule) */}
      <TraceFilterBar
        search={search}
        selectedGroup={selectedGroup}
        statusFilter={statusFilter}
        groups={groups}
        loading={loading}
        onSearchChange={setSearch}
        onGroupChange={setSelectedGroup}
        onStatusChange={setStatusFilter}
        onDateRangeChange={setDateRange}
        onRefresh={refresh}
      />

      {/* 紧凑数据表格 (Widget Organism) */}
      <TraceTable
        traces={traces}
        total={total}
        loading={loading}
        page={page}
        pageSize={pageSize}
        onViewTrace={onViewTrace}
        onTableChange={handleTableChange}
      />
    </Card>
  );
};
