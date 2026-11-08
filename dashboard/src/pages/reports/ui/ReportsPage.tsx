import { useState } from "react";
import type { useReportsViewModel } from "../model/useReportsViewModel";
import type { ReportItem } from "../../../entities/report/model/types";
import { NativeSelect } from "../../../shared/ui/native-select";
import { Pagination } from "../../../shared/ui/pagination";
import { ReportPreviewModal } from "../../../widgets/report-preview-modal/ReportPreviewModal";
import { ReportList } from "../../../widgets/report-list/ReportList";
import { ReportFilterBar } from "../../../features/filter-reports/ui/ReportFilterBar";
import { RerenderReportModal } from "../../../features/rerender-report/ui/RerenderReportModal";

interface ReportsPageProps {
  viewModel: ReturnType<typeof useReportsViewModel>;
  onViewTrace?: (traceId: string) => void;
}

export function ReportsPage({ viewModel: vm, onViewTrace }: ReportsPageProps) {
  const [rerenderingReport, setRerenderingReport] = useState<ReportItem | null>(null);

  return (
    <div className="space-y-5">
      <ReportFilterBar
        search={vm.search}
        selectedPlatform={vm.selectedPlatform}
        onPlatformChange={vm.setSelectedPlatform}
        selectedGroup={vm.selectedGroup}
        dateRange={vm.dateRange}
        groups={vm.groups}
        loading={vm.loading}
        onSearchChange={vm.setSearch}
        onGroupChange={vm.setSelectedGroup}
        onDateRangeChange={vm.setDateRange}
        onReset={vm.resetFilters}
        onRefresh={() => vm.refresh(false)}
      />
      {vm.hasUpdates && (
        <p role="status" className="text-sm text-secondary-ink">
          报告有更新，点击“刷新”查看。当前页保持不变。
        </p>
      )}
      {vm.groupsError && (
        <p role="alert" className="m-0 text-sm text-destructive">
          {vm.groupsError}
        </p>
      )}
      {vm.error && (
        <p role="alert" className="m-0 text-sm text-destructive">
          {vm.error}
          {vm.rawReports.length > 0 && ` 当前保留第 ${vm.loadedPage} 页上次读取的报告。`}
        </p>
      )}
      {vm.downloadError && (
        <p role="alert" className="m-0 text-sm text-destructive">
          {vm.downloadError}
        </p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-4">
        <span className="text-sm text-muted-foreground">
          {`共 ${vm.total} 份报告 · 本页 ${vm.reports.length} 份`}
        </span>
        <label className="flex items-center gap-2 whitespace-nowrap text-sm text-muted-foreground">
          时间排序
          <span className="block w-36">
            <NativeSelect
              value={vm.sortOrder}
              onChange={(event) => vm.setSortOrder(event.target.value === "asc" ? "asc" : "desc")}
            >
              <option value="desc">从新到旧</option>
              <option value="asc">从旧到新</option>
            </NativeSelect>
          </span>
        </label>
      </div>
      {vm.loading && (
        <p role="status" className="m-0 text-sm text-muted-foreground">
          正在读取报告…
        </p>
      )}
      {vm.reports.length > 0 ? (
        <ReportList
          reports={vm.reports}
          downloadingFiles={vm.downloadingFiles}
          onPreview={vm.openPreview}
          onDownload={vm.downloadReport}
          onRerender={setRerenderingReport}
          onViewTrace={onViewTrace}
        />
      ) : !vm.loading && !vm.error ? (
        <p role="status" className="py-12 text-center text-muted-foreground">
          暂无符合条件的报告，可调整筛选或发起分析。
        </p>
      ) : null}
      {vm.total > 0 && (
        <Pagination
          page={vm.page}
          pageSize={vm.pageSize}
          total={vm.total}
          pageSizes={[10, 20, 50]}
          disabled={vm.loading}
          onChange={vm.handlePageChange}
        />
      )}
      <ReportPreviewModal
        open={vm.previewOpen}
        loading={vm.previewLoading}
        error={vm.previewError}
        report={vm.selectedReport}
        downloading={Boolean(
          vm.selectedReport && vm.downloadingFiles.has(vm.selectedReport.filename),
        )}
        onClose={vm.closePreview}
        onDownload={vm.downloadReport}
      />
      <RerenderReportModal
        open={Boolean(rerenderingReport)}
        report={rerenderingReport}
        onClose={() => setRerenderingReport(null)}
        onSuccess={() => vm.refresh(false, true)}
      />
    </div>
  );
}
