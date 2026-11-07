import { useState } from "react";
import { IconCopy } from "@tabler/icons-react";
import type { PluginLogItem } from "../../../entities/log/model/types";
import { copyToClipboard } from "../../../shared/lib/clipboard";
import { Button } from "../../../shared/ui/button";

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
              title="复制当前任务日志，也可在日志区域按 Ctrl+A 或 Command+A 全选复制"
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
                void copyLogs();
              }
            }}
            className="max-h-80 overflow-auto rounded-xl bg-muted p-3 font-mono text-xs leading-6 outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            {logs.map((log) => (
              <div
                key={log.id}
                className={`whitespace-pre-wrap break-words ${["ERROR", "CRITICAL"].includes(log.level) ? "text-destructive" : "text-foreground"}`}
              >
                <span className="text-muted-foreground">{log.time_str} </span>
                <span>[{log.level}] </span>
                {log.tag && <span>[{log.tag}] </span>}
                <span className="text-muted-foreground">[{log.location || log.logger_name}] </span>
                {log.function_name && <span>[{log.function_name}()] </span>}
                {log.message}
              </div>
            ))}
          </div>
        </>
      ) : (
        <p className="text-sm text-muted-foreground">暂无日志，也可能已被内存日志队列清理。</p>
      )}
    </details>
  );
}
