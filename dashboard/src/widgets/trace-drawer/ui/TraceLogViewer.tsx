import { useState } from "react";
import { IconCopy } from "@tabler/icons-react";
import type { PluginLogItem } from "@/entities/log/model/types";
import { LogEntry } from "@/entities/log/ui/LogEntry";
import { copyToClipboard } from "@/shared/lib/clipboard";
import { Button } from "@/shared/ui/button";

export function TraceLogViewer({ logs }: { logs: PluginLogItem[] }) {
  const [copyResult, setCopyResult] = useState("");
  const copyLogs = async () => {
    const text = logs
      .map(
        (log) =>
          log.raw ||
          `[${log.time_str}] [${log.level}] ${log.location ? `[${log.location}] ` : ""}${log.function_name ? `[${log.function_name}] ` : ""}${log.tag ? `[${log.tag}] ` : ""}${log.message}`,
      )
      .join("\n");
    setCopyResult((await copyToClipboard(text)) ? "已复制日志" : "无法复制，请手动选择日志内容。");
  };
  return (
    <details open className="border-0 border-t border-solid border-border pt-4">
      <summary className="cursor-pointer font-medium focus-visible:outline-2 focus-visible:outline-ring">
        任务日志 · {logs.length} 条
      </summary>
      {logs.length ? (
        <>
          <div className="my-2 flex items-center gap-2">
            <Button
              size="sm"
              variant="outline"
              onClick={() => void copyLogs()}
              title="复制当前任务日志；日志区域支持 Ctrl+A 全选、Ctrl+C 复制（Mac 使用 Command）"
            >
              <IconCopy aria-hidden="true" />
              复制日志
            </Button>
            {copyResult && (
              <span role="status" className="text-sm text-muted-foreground">
                {copyResult}
              </span>
            )}
          </div>
          <div
            tabIndex={0}
            role="region"
            aria-label="任务日志内容"
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
            className="max-h-80 overflow-auto rounded-xl border border-solid border-border bg-card p-2 font-sans text-[13px] leading-5 outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {logs.map((log) => (
              <LogEntry key={log.id} item={log} />
            ))}
          </div>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">暂无日志，也可能已被内存日志队列清理。</p>
      )}
    </details>
  );
}
