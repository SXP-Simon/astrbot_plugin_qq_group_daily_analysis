import { IconRefresh, IconPlayerPlay } from "@tabler/icons-react";
import { Dialog, DialogContent, DialogTitle, DialogDescription } from "../../shared/ui/dialog";
import { Button } from "../../shared/ui/button";
import { StatusTag } from "../../shared/ui/StatusTag";
import { SpanTimeline } from "../../entities/trace/ui/SpanTimeline";
import { TraceMetricsChart } from "../../entities/trace/ui/TraceMetricsChart";
import { formatStageName } from "../../shared/lib/formatters";
import { ResumeTaskModal } from "../../features/resume-task/ui/ResumeTaskModal";
import { ReportPreviewModal } from "../report-preview-modal/ReportPreviewModal";
import { TraceLogViewer } from "./ui/TraceLogViewer";
import { TraceSummaryCard } from "./ui/TraceSummaryCard";
import { useTraceDrawerViewModel } from "./model/useTraceDrawerViewModel";

interface TraceDrawerProps {
  traceId: string | null;
  open: boolean;
  onClose: () => void;
}

export function TraceDrawer({ traceId, open, onClose }: TraceDrawerProps) {
  const vm = useTraceDrawerViewModel(traceId, open);
  const trace = vm.trace;
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next && !vm.resuming) onClose();
      }}
    >
      <DialogContent className="max-w-6xl gap-5 sm:p-7">
        <div className="flex flex-wrap items-start justify-between gap-3 pr-6">
          <div className="grid gap-1">
            <DialogTitle>{trace?.group_name || "任务详情"}</DialogTitle>
            <DialogDescription className="flex flex-wrap items-center gap-2">
              {trace && (
                <>
                  <StatusTag status={vm.effectiveStatus} />
                  <span className="font-mono text-xs">
                    {trace.platform} · {trace.group_id}
                  </span>
                </>
              )}
              {!trace && "查看阶段记录、日志与报告"}
            </DialogDescription>
          </div>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={vm.refresh}
              disabled={vm.loading || vm.refreshing}
            >
              <IconRefresh
                aria-hidden="true"
                className={vm.loading || vm.refreshing ? "animate-spin" : undefined}
              />
              刷新
            </Button>
            {trace && trace.status !== "running" && (
              <Button size="sm" onClick={() => vm.setResumeModalOpen(true)} disabled={vm.resuming}>
                <IconPlayerPlay aria-hidden="true" />
                继续分析
              </Button>
            )}
          </div>
        </div>
        {vm.error && (
          <p role="alert" className="m-0 text-sm text-destructive">
            {vm.error}
          </p>
        )}
        {vm.actionError && !vm.resumeModalOpen && (
          <p role="alert" className="m-0 text-sm text-destructive">
            {vm.actionError}
          </p>
        )}
        {vm.notice && (
          <p role="status" className="m-0 text-sm text-muted-foreground">
            {vm.notice}
          </p>
        )}
        {vm.loading ? (
          <p role="status" className="py-12 text-center text-muted-foreground">
            正在加载任务详情…
          </p>
        ) : (
          trace && (
            <>
              {trace.status === "running" && (
                <p role="status" className="m-0 rounded-xl bg-accent px-4 py-3 text-sm">
                  正在{trace.current_stage ? formatStageName(trace.current_stage) : "准备分析"}
                  ，详情自动更新。
                </p>
              )}
              {trace.status === "skipped" && (
                <p className="m-0 rounded-xl bg-muted px-4 py-3 text-sm">
                  {trace.error_message || "本次任务已跳过，具体原因未记录。"}
                </p>
              )}
              {trace.status === "failed" && (
                <div
                  role="alert"
                  className="rounded-xl border border-solid border-destructive/35 bg-destructive/5 px-4 py-3"
                >
                  <p className="m-0 font-medium text-destructive">
                    {trace.error_stage ? `${formatStageName(trace.error_stage)}失败` : "分析未完成"}
                  </p>
                  <p className="mb-0 mt-1 whitespace-pre-wrap break-words text-sm">
                    {trace.error_message || "未记录具体原因，请查看阶段记录和日志。"}
                  </p>
                </div>
              )}
              <TraceSummaryCard
                trace={trace}
                downloading={vm.downloading}
                onPreviewFile={vm.previewFile}
                onDownloadFile={vm.downloadFile}
              />
              <section
                aria-label="执行过程"
                className="border-0 border-t border-solid border-border pt-4"
              >
                <h2 className="mb-3 mt-0 text-lg font-medium">执行过程</h2>
                <SpanTimeline
                  spans={trace.spans || []}
                  totalDurationMs={trace.duration_ms ?? undefined}
                  currentStage={trace.current_stage ?? undefined}
                  taskStatus={trace.status}
                />
              </section>
              <details className="border-0 border-t border-solid border-border pt-4">
                <summary className="cursor-pointer font-medium focus-visible:outline-2 focus-visible:outline-ring">
                  耗时、内存与传输
                </summary>
                <div className="mt-3">
                  <TraceMetricsChart trace={trace} />
                </div>
              </details>
              {vm.logsError && (
                <p role="alert" className="m-0 text-sm text-destructive">
                  {vm.logsError}
                </p>
              )}
              <TraceLogViewer key={trace.trace_id} logs={vm.logs} />
              {trace.stack_trace && (
                <details>
                  <summary className="cursor-pointer focus-visible:outline-2 focus-visible:outline-ring">
                    异常堆栈
                  </summary>
                  <pre className="max-h-80 overflow-auto rounded-xl bg-muted p-3 text-xs whitespace-pre-wrap break-words">
                    {trace.stack_trace}
                  </pre>
                </details>
              )}
              <details>
                <summary className="cursor-pointer text-sm text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring">
                  完整任务记录
                </summary>
                <pre className="max-h-96 overflow-auto rounded-xl bg-muted p-3 text-xs whitespace-pre-wrap break-words">
                  {JSON.stringify(trace, null, 2)}
                </pre>
              </details>
            </>
          )
        )}
        <ReportPreviewModal
          open={vm.previewOpen}
          loading={vm.previewLoading}
          report={vm.previewReport}
          error={vm.previewError || vm.actionError}
          downloading={vm.downloading}
          onClose={vm.closePreview}
          onDownload={(report) => void vm.downloadFile(report.filename, Boolean(report.is_html))}
        />
        <ResumeTaskModal
          open={vm.resumeModalOpen}
          loading={vm.resuming}
          error={vm.actionError}
          onCancel={() => vm.setResumeModalOpen(false)}
          onConfirm={vm.confirmResume}
        />
      </DialogContent>
    </Dialog>
  );
}
