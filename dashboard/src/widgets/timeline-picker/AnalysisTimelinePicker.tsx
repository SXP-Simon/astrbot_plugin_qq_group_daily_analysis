import { useEffect, useRef, useState } from "react";
import { IconChevronLeft, IconChevronRight } from "@tabler/icons-react";
import type { TraceRecord } from "../../entities/trace/model/types";
import { Button } from "../../shared/ui/button";
import { StatusTag } from "../../shared/ui/StatusTag";
import { formatTimestamp, formatDuration } from "../../shared/lib/formatters";

interface AnalysisTimelinePickerProps {
  traces: TraceRecord[];
  selectedTrace: TraceRecord | null;
  onSelectTrace: (trace: TraceRecord) => void;
  onViewTraceDetail?: (traceId: string) => void;
  loading?: boolean;
}

const recorded = (value: number | null | undefined) =>
  typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;

export function AnalysisTimelinePicker({
  traces,
  selectedTrace,
  onSelectTrace,
  onViewTraceDetail,
  loading = false,
}: AnalysisTimelinePickerProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const nodes = useRef(new Map<string, HTMLButtonElement>());
  const drag = useRef<{ start: number; scroll: number } | null>(null);
  const moved = useRef(false);
  const [dragging, setDragging] = useState(false);
  const selectedId = selectedTrace?.trace_id;
  const selectedIndex = traces.findIndex((trace) => trace.trace_id === selectedId);

  useEffect(() => {
    if (selectedIndex < 0 || !selectedId) return;
    const frame = requestAnimationFrame(() => {
      const container = containerRef.current;
      const node = nodes.current.get(selectedId);
      if (!container || !node) return;
      const left = node.offsetLeft + node.offsetWidth / 2 - container.clientWidth / 2;
      container.scrollTo({
        left: Math.max(0, Math.min(container.scrollWidth - container.clientWidth, left)),
        behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth",
      });
    });
    // 快速切换仅让最后一次选择调整横向位置，不滚动整个页面。
    return () => cancelAnimationFrame(frame);
  }, [selectedId, selectedIndex, traces.length]);

  if (traces.length === 0) return null;

  return (
    <section aria-label="按时间切换任务" className="min-w-0 space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm text-muted-foreground">
          按时间倒序{selectedIndex >= 0 && ` · ${selectedIndex + 1} / ${traces.length}`}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            disabled={selectedIndex <= 0 || loading}
            onClick={() => onSelectTrace(traces[selectedIndex - 1])}
          >
            <IconChevronLeft aria-hidden="true" />
            上一条
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={selectedIndex < 0 || selectedIndex >= traces.length - 1 || loading}
            onClick={() => onSelectTrace(traces[selectedIndex + 1])}
          >
            下一条
            <IconChevronRight aria-hidden="true" />
          </Button>
          {onViewTraceDetail && selectedTrace && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onViewTraceDetail(selectedTrace.trace_id)}
            >
              查看所选任务
            </Button>
          )}
        </div>
      </div>
      <div
        ref={containerRef}
        className={`relative overflow-x-auto overscroll-x-contain pb-2 ${dragging ? "cursor-grabbing" : ""}`}
        onPointerDown={(event) => {
          if (event.pointerType !== "mouse" || event.button !== 0) return;
          moved.current = false;
          drag.current = { start: event.clientX, scroll: event.currentTarget.scrollLeft };
        }}
        onPointerMove={(event) => {
          if (!drag.current) return;
          const distance = event.clientX - drag.current.start;
          if (Math.abs(distance) <= 5 && !moved.current) return;
          event.preventDefault();
          moved.current = true;
          setDragging(true);
          event.currentTarget.scrollLeft = drag.current.scroll - distance;
        }}
        onPointerUp={() => {
          drag.current = null;
          setDragging(false);
        }}
        onPointerCancel={() => {
          drag.current = null;
          setDragging(false);
        }}
        onPointerLeave={() => {
          drag.current = null;
          setDragging(false);
        }}
        onDragStart={(event) => event.preventDefault()}
      >
        <ol className="m-0 flex w-max min-w-full list-none gap-2 p-1">
          {traces.map((trace, index) => {
            const isSelected = trace.trace_id === selectedId;
            const item = isSelected && selectedTrace ? { ...trace, ...selectedTrace } : trace;
            const tokens = recorded(item.total_tokens ?? item.token_usage?.total_tokens);
            const ratio = recorded(
              item.compression_ratio ?? item.context_metrics?.compression_ratio,
            );
            const duration = recorded(item.duration_ms);
            return (
              <li key={trace.trace_id}>
                <Button
                  ref={(node) => {
                    if (node) nodes.current.set(trace.trace_id, node);
                    else nodes.current.delete(trace.trace_id);
                  }}
                  variant={isSelected ? "secondary" : "ghost"}
                  disabled={loading}
                  aria-pressed={isSelected}
                  aria-label={`选择任务 ${trace.group_name || trace.group_id} · ${trace.platform} · ${formatTimestamp(trace.started_at)} · ${trace.trace_id}`}
                  tabIndex={index === (selectedIndex < 0 ? 0 : selectedIndex) ? 0 : -1}
                  className="grid h-auto w-60 select-none gap-2 whitespace-normal p-3 text-left font-normal"
                  onClick={(event) => {
                    if (!moved.current || event.detail === 0) onSelectTrace(trace);
                  }}
                  onKeyDown={(event) => {
                    const target =
                      event.key === "ArrowRight"
                        ? Math.min(index + 1, traces.length - 1)
                        : event.key === "ArrowLeft"
                          ? Math.max(index - 1, 0)
                          : event.key === "Home"
                            ? 0
                            : event.key === "End"
                              ? traces.length - 1
                              : null;
                    if (target === null) return;
                    event.preventDefault();
                    onSelectTrace(traces[target]);
                    nodes.current.get(traces[target].trace_id)?.focus({ preventScroll: true });
                  }}
                >
                  <span className="flex items-center justify-between gap-2">
                    <span className="truncate font-medium">
                      {trace.group_name || trace.group_id}
                    </span>
                    <StatusTag status={trace.status} />
                  </span>
                  <span className="truncate text-xs text-muted-foreground">
                    {trace.platform} · {trace.group_id}
                  </span>
                  <span className="font-mono text-xs text-muted-foreground">
                    {formatTimestamp(trace.started_at)}
                  </span>
                  <span className="text-xs">
                    Tokens {tokens === null ? "未记录" : tokens.toLocaleString()} · 耗时{" "}
                    {duration === null
                      ? "未记录"
                      : duration === 0
                        ? "0ms"
                        : formatDuration(duration)}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    消息留存{" "}
                    {ratio === null || ratio > 1
                      ? "未记录"
                      : `${Number((ratio * 100).toFixed(1))}%`}
                  </span>
                </Button>
              </li>
            );
          })}
        </ol>
      </div>
    </section>
  );
}
