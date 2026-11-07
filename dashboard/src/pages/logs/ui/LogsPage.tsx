import { useRef, useState } from "react";
import {
  IconAlertCircle,
  IconAlertTriangle,
  IconArrowUp,
  IconPlayerPause,
} from "@tabler/icons-react";
import type { useLogsViewModel } from "../model/useLogsViewModel";
import { LogFilterBar } from "../../../features/filter-logs/ui/LogFilterBar";
import { TAG_STYLE_MAP } from "../../../entities/log/model/types";
import { Button } from "../../../shared/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "../../../shared/ui/dialog";

interface LogsPageProps {
  viewModel: ReturnType<typeof useLogsViewModel>;
  onViewTrace: (traceId: string) => void;
}

const levelStyles: Record<string, string> = {
  DEBUG: "bg-creative/15 text-creative",
  INFO: "bg-info/15 text-info",
  WARNING: "bg-warning/15 text-warning",
  ERROR: "bg-destructive/15 text-destructive",
  CRITICAL: "bg-destructive text-destructive-foreground",
};

export function LogsPage({ viewModel: vm, onViewTrace }: LogsPageProps) {
  const logBox = useRef<HTMLDivElement>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const cancelButton = useRef<HTMLButtonElement>(null);
  return (
    <section aria-label="运行日志" className="space-y-4">
      <LogFilterBar
        search={vm.search}
        level={vm.level}
        tag={vm.tag}
        availableTags={vm.availableTags}
        autoRefresh={vm.autoRefresh}
        loading={vm.loading}
        clearing={vm.clearing}
        onSearchChange={vm.setSearch}
        onLevelChange={vm.setLevel}
        onTagChange={vm.setTag}
        onAutoRefreshChange={vm.setAutoRefresh}
        onRefresh={() => void vm.refresh()}
        onClear={() => setConfirmClear(true)}
        onCopyAll={() => void vm.copyLogs()}
      />
      {vm.error && (
        <p role="alert" className="text-sm text-destructive">
          {vm.error}
          {vm.logs.length > 0 && " 已有日志仍可查看。"}
        </p>
      )}
      {vm.feedback && (
        <p role="status" className="text-sm text-muted-foreground">
          {vm.feedback}
        </p>
      )}
      <div className="flex min-h-8 flex-wrap items-center justify-between gap-2 text-sm text-muted-foreground">
        <div className="flex flex-wrap items-center gap-3">
          <span>
            显示 {vm.logs.length} 条 / 匹配 {vm.total} 条
          </span>
          <span
            className={`inline-flex items-center gap-1.5 rounded-lg px-2 py-1 text-xs font-medium ${vm.autoRefresh ? "bg-success/15 text-success" : "bg-warning/15 text-warning"}`}
          >
            {vm.autoRefresh ? (
              <span aria-hidden="true" className="size-1.5 rounded-full bg-current" />
            ) : (
              <IconPlayerPause aria-hidden="true" className="size-3.5" />
            )}
            {vm.autoRefresh ? "实时更新" : "已暂停更新"}
          </span>
        </div>
        {scrolled && (
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              logBox.current?.scrollTo({ top: 0, behavior: "instant" });
              logBox.current?.focus({ preventScroll: true });
            }}
          >
            <IconArrowUp aria-hidden="true" />
            回到最新
          </Button>
        )}
      </div>
      <div
        ref={logBox}
        role="region"
        aria-label="日志内容"
        tabIndex={0}
        aria-busy={vm.loading}
        onScroll={(event) => setScrolled(event.currentTarget.scrollTop > 80)}
        onKeyDown={(event) => {
          if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "a") {
            event.preventDefault();
            const range = document.createRange();
            range.selectNodeContents(event.currentTarget);
            const selection = window.getSelection();
            selection?.removeAllRanges();
            selection?.addRange(range);
          }
        }}
        className="h-[60dvh] min-h-80 space-y-1 overflow-auto rounded-xl border border-solid border-border bg-card p-3 font-mono text-[13px] leading-6 outline-none focus-visible:ring-2 focus-visible:ring-ring sm:p-4"
      >
        {!vm.logs.length ? (
          <p className="py-12 text-center text-muted-foreground">
            {vm.loading ? "正在加载日志…" : "暂无匹配的插件运行日志"}
          </p>
        ) : (
          vm.logs.map((item) => (
            <div
              key={item.id}
              className={`border-0 border-l-2 border-solid px-3 py-2 ${
                ["ERROR", "CRITICAL"].includes(item.level)
                  ? "border-destructive bg-destructive/5"
                  : item.level === "WARNING"
                    ? "border-warning bg-warning/5"
                    : "border-transparent"
              }`}
            >
              <div className="flex flex-wrap items-center gap-x-3 text-muted-foreground">
                <time>{item.time_str}</time>
                <span
                  className={`inline-flex items-center gap-1 rounded-md px-2 text-xs font-medium ${levelStyles[item.level] ?? "bg-muted text-muted-foreground"}`}
                >
                  {item.level === "WARNING" && (
                    <IconAlertTriangle aria-hidden="true" className="size-3.5" />
                  )}
                  {["ERROR", "CRITICAL"].includes(item.level) && (
                    <IconAlertCircle aria-hidden="true" className="size-3.5" />
                  )}
                  {item.level}
                </span>
                <span title={TAG_STYLE_MAP[item.tag]?.label}>{item.tag}</span>
                {item.location && <span className="break-all">{item.location}</span>}
                {item.stage && <span className="break-all">{item.stage}</span>}
                {item.trace_id && (
                  <Button
                    size="sm"
                    variant="link"
                    className="h-auto whitespace-normal break-all p-0 font-mono text-xs text-info decoration-info/40 hover:text-info hover:decoration-info"
                    onClick={() => {
                      if (item.trace_id) onViewTrace(item.trace_id);
                    }}
                  >
                    查看任务 {item.trace_id}
                  </Button>
                )}
              </div>
              <div
                className={
                  "whitespace-pre-wrap break-words " +
                  (["ERROR", "CRITICAL"].includes(item.level)
                    ? "text-destructive"
                    : "text-foreground")
                }
              >
                {item.message}
              </div>
            </div>
          ))
        )}
      </div>
      <Dialog
        open={confirmClear}
        onOpenChange={(open) => {
          if (!vm.clearing) setConfirmClear(open);
        }}
      >
        <DialogContent
          onOpenAutoFocus={(event) => {
            event.preventDefault();
            cancelButton.current?.focus();
          }}
        >
          <DialogTitle>清空日志缓冲？</DialogTitle>
          <DialogDescription>
            将清空插件当前缓存的全部运行日志，包括被筛选隐藏的记录。不会删除报告文件；新日志仍会继续记录。
          </DialogDescription>
          {vm.error && (
            <p role="alert" className="text-sm text-destructive">
              {vm.error}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button
              ref={cancelButton}
              variant="outline"
              disabled={vm.clearing}
              onClick={() => setConfirmClear(false)}
            >
              取消
            </Button>
            <Button
              variant="destructive"
              disabled={vm.clearing}
              onClick={async () => {
                if (await vm.clearLogs()) setConfirmClear(false);
              }}
            >
              {vm.clearing ? "正在清空…" : "确认清空"}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
}
