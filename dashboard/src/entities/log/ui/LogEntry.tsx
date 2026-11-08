import { IconAlertCircle, IconAlertTriangle } from "@tabler/icons-react";
import { TAG_STYLE_MAP, type PluginLogItem } from "../model/types";
import { Button } from "../../../shared/ui/button";

const levelStyles: Record<string, string> = {
  DEBUG: "bg-creative/15 text-creative",
  INFO: "bg-info/15 text-info",
  WARNING: "bg-warning/15 text-warning",
  ERROR: "bg-destructive/15 text-destructive",
  CRITICAL: "bg-destructive text-destructive-foreground",
};

/** 日志页和任务详情共用等级配色、调用位置与模块名称。 */
export function LogEntry({
  item,
  onViewTrace,
}: {
  item: PluginLogItem;
  onViewTrace?: (traceId: string) => void;
}) {
  return (
    <div
      className={`break-words border-0 border-b border-l-2 border-solid border-b-border/40 px-2 py-0.5 [overflow-wrap:anywhere] last:border-b-0 ${
        ["ERROR", "CRITICAL"].includes(item.level)
          ? "border-l-destructive bg-destructive/5"
          : item.level === "WARNING"
            ? "border-l-warning bg-warning/5"
            : "border-l-transparent"
      }`}
    >
      <span className="text-muted-foreground">
        <time className="mr-2 whitespace-nowrap">{item.time_str}</time>
        <span
          className={`mr-2 inline-flex items-center gap-1 rounded px-1 align-baseline text-xs font-medium ${levelStyles[item.level] ?? "bg-muted text-muted-foreground"}`}
        >
          {item.level === "WARNING" && (
            <IconAlertTriangle aria-hidden="true" className="size-3.5" />
          )}
          {["ERROR", "CRITICAL"].includes(item.level) && (
            <IconAlertCircle aria-hidden="true" className="size-3.5" />
          )}
          {item.level}
        </span>
        <span className="mr-2" title={item.tag}>
          {TAG_STYLE_MAP[item.tag]?.label ?? item.tag}
        </span>
        <span className="mr-2" title="日志调用位置">
          [{item.location || item.logger_name}
          {item.function_name && <> {item.function_name}()</>}]
        </span>
        {item.stage && <span className="mr-2">{item.stage}</span>}
        {item.trace_id && onViewTrace && (
          <Button
            size="sm"
            variant="link"
            className="mr-2 inline h-auto max-w-full whitespace-normal p-0 align-baseline font-sans text-xs font-normal text-secondary-ink decoration-secondary-line [overflow-wrap:anywhere] hover:text-secondary-ink hover:decoration-secondary-ink"
            onClick={() => {
              if (item.trace_id) onViewTrace(item.trace_id);
            }}
          >
            查看任务 {item.trace_id}
          </Button>
        )}
      </span>
      <span
        className={
          "whitespace-pre-wrap break-words " +
          (["ERROR", "CRITICAL"].includes(item.level) ? "text-destructive" : "text-foreground")
        }
      >
        {item.message}
      </span>
    </div>
  );
}
