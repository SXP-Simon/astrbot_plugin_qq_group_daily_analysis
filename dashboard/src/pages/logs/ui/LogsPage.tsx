import { useRef, useState } from "react";
import { IconAlertTriangle, IconArrowUp } from "@tabler/icons-react";
import type { useLogsViewModel } from "../model/useLogsViewModel";
import { LogFilterBar } from "../../../features/filter-logs/ui/LogFilterBar";
import { TAG_STYLE_MAP } from "../../../entities/log/model/types";
import { Button } from "../../../shared/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "../../../shared/ui/dialog";

interface LogsPageProps {
  viewModel: ReturnType<typeof useLogsViewModel>;
  onViewTrace: (traceId: string) => void;
}

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
        <span>
          显示 {vm.logs.length} 条 / 匹配 {vm.total} 条 ·{" "}
          {vm.autoRefresh ? "实时更新" : "已暂停更新"}
        </span>
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
        className="h-[60dvh] min-h-80 overflow-auto rounded-xl border border-solid border-border bg-card p-3 font-mono text-xs leading-6 outline-none focus-visible:ring-2 focus-visible:ring-ring sm:p-4"
      >
        {!vm.logs.length ? (
          <p className="py-12 text-center text-muted-foreground">
            {vm.loading ? "正在加载日志…" : "暂无匹配的插件运行日志"}
          </p>
        ) : (
          vm.logs.map((item) => (
            <div
              key={item.id}
              className="border-0 border-b border-solid border-border/50 py-2 last:border-0"
            >
              <div className="flex flex-wrap items-center gap-x-3 text-muted-foreground">
                <time>{item.time_str}</time>
                <span
                  className={
                    ["ERROR", "CRITICAL"].includes(item.level)
                      ? "text-destructive"
                      : "text-foreground"
                  }
                >
                  {item.level === "WARNING" && (
                    <IconAlertTriangle
                      aria-hidden="true"
                      className="mr-1 inline size-3.5 align-middle"
                    />
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
                    className="h-auto whitespace-normal break-all p-0 font-mono text-xs"
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
