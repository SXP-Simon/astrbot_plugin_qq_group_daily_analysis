import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { IconArrowLeft } from "@tabler/icons-react";
import { Button } from "../../../shared/ui/button";
import type { TraceSpan } from "../model/types";
import { resolveSpanOutcome } from "../model/spanOutcome";
import { buildSpanTree, type SpanTreeNode } from "../model/spanTree";
import { getSpanTiming } from "../model/spanTiming";
import { getRenderAttemptDiagnostic } from "../model/renderAttempts";
import { formatStageName } from "../../../shared/lib/formatters";
import { StageMetricsBadges } from "./StageMetricsBadges";
import { PromptsInspector } from "./PromptsInspector";
import { SpanPayloadViewer } from "./SpanPayloadViewer";
import { SpanHeader } from "./SpanHeader";
import { SpanAlerts } from "./SpanAlerts";
import { LlmAttemptsTable } from "./LlmAttemptsTable";
import { RenderAttemptsTable } from "./RenderAttemptsTable";
import "./SpanTimeline.css";

interface SpanTimelineProps {
  spans: TraceSpan[];
  totalDurationMs?: number;
  currentStage?: string;
  taskStatus?: string;
}

export function SpanTimeline({
  spans,
  totalDurationMs,
  currentStage,
  taskStatus,
}: SpanTimelineProps) {
  const roots = useMemo(() => buildSpanTree(spans), [spans]);
  const flat = useMemo(() => {
    const result: { node: SpanTreeNode; parent?: TraceSpan }[] = [];
    const pending: typeof result = roots.map((node) => ({ node }));
    while (pending.length) {
      const item = pending.shift()!;
      result.push(item);
      pending.unshift(...item.node.children.map((node) => ({ node, parent: item.node.span })));
    }
    return result;
  }, [roots]);
  const traceId = spans[0]?.trace_id ?? "";
  const [selection, setSelection] = useState<{
    traceId: string;
    spanId: string;
    expanded: Set<string>;
  } | null>(null);
  const [now, setNow] = useState(Date.now);
  const inspectionRef = useRef<HTMLDivElement>(null);
  const evidenceHeadingRef = useRef<HTMLHeadingElement>(null);
  const treeRef = useRef<HTMLElement>(null);
  const moveFocusToEvidence = useRef(false);
  useLayoutEffect(() => {
    if (!moveFocusToEvidence.current) return;
    moveFocusToEvidence.current = false;
    const width = inspectionRef.current?.clientWidth ?? 0;
    if (width > 0 && width <= 700) {
      evidenceHeadingRef.current?.focus({ preventScroll: true });
      evidenceHeadingRef.current?.scrollIntoView({ block: "start" });
    }
  });
  const hasLive = spans.some((span) => getSpanTiming(span, taskStatus).live);
  useEffect(() => {
    if (!hasLive) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [hasLive]);

  // 用户尚未选择时定位正在执行或异常最深处；切换任务不沿用上个任务的阶段。
  const preferred =
    (taskStatus === "running"
      ? [...flat].reverse().find(({ node }) => node.span.status === "running")
      : undefined) ??
    [...flat]
      .reverse()
      .find(({ node }) =>
        ["failed", "warning"].includes(resolveSpanOutcome(node.span.status, node.span.payload)),
      ) ??
    [...flat].reverse().find(({ node }) => getRenderAttemptDiagnostic(node.span.payload)) ??
    flat[0];
  const initialExpanded = new Set<string>();
  let parent = preferred?.parent;
  while (parent) {
    initialExpanded.add(parent.span_id);
    parent = flat.find(({ node }) => node.span.span_id === parent?.span_id)?.parent;
  }
  const active =
    selection?.traceId === traceId &&
    flat.some(({ node }) => node.span.span_id === selection.spanId)
      ? selection
      : { traceId, spanId: preferred?.node.span.span_id ?? "", expanded: initialExpanded };
  const selected = flat.find(({ node }) => node.span.span_id === active.spanId)?.node;
  const payload = selected?.span.payload;
  const llmAttempts = Array.isArray(payload?.llm_attempts)
    ? payload.llm_attempts.filter(
        (value): value is Record<string, unknown> =>
          value !== null && typeof value === "object" && !Array.isArray(value),
      )
    : [];
  const renderAttempts = Array.isArray(payload?.render_attempts)
    ? payload.render_attempts.filter(
        (value): value is Record<string, unknown> =>
          value !== null && typeof value === "object" && !Array.isArray(value),
      )
    : [];

  const renderBranch = (nodes: SpanTreeNode[], parentSpan?: TraceSpan) => (
    <ul className="stage-branch">
      {nodes.map((node) => {
        const span = node.span;
        const expanded = active.expanded.has(span.span_id);
        return (
          <li key={span.span_id}>
            <SpanHeader
              stageName={span.stage_name}
              durationMs={span.duration_ms}
              startedAt={span.started_at}
              totalDurationMs={
                parentSpan ? getSpanTiming(parentSpan, taskStatus, now).durationMs : totalDurationMs
              }
              parentStageName={parentSpan?.stage_name}
              status={span.status}
              taskStatus={taskStatus}
              now={now}
              hasChildren={node.children.length > 0}
              isExpanded={expanded}
              isSelected={span.span_id === active.spanId}
              payload={span.payload}
              onToggleExpand={() => {
                const next = new Set(active.expanded);
                if (expanded) next.delete(span.span_id);
                else next.add(span.span_id);
                moveFocusToEvidence.current = true;
                setSelection({ traceId, spanId: span.span_id, expanded: next });
              }}
            />
            {expanded && node.children.length > 0 && renderBranch(node.children, span)}
          </li>
        );
      })}
    </ul>
  );

  return (
    <div className="stage-inspection" ref={inspectionRef}>
      {taskStatus === "running" &&
        currentStage &&
        !spans.some((span) => span.stage_name.toUpperCase() === currentStage.toUpperCase()) && (
          <p className="stage-missing">
            正在{formatStageName(currentStage)}，尚未收到该阶段的详细记录。
          </p>
        )}
      {roots.length === 0 ? (
        <p className="stage-missing">
          {taskStatus === "running" ? "正在等待执行阶段记录" : "无执行阶段记录"}
        </p>
      ) : (
        <div className="stage-diagnostics">
          <nav aria-label="执行阶段" className="stage-tree" ref={treeRef}>
            {renderBranch(roots)}
          </nav>
          <section className="stage-evidence" aria-label="阶段详情">
            <h3 ref={evidenceHeadingRef} tabIndex={-1}>
              阶段详情{selected ? ` · ${formatStageName(selected.span.stage_name)}` : ""}
            </h3>
            <Button
              className="stage-return"
              size="sm"
              variant="outline"
              onClick={() => {
                const button =
                  treeRef.current?.querySelector<HTMLButtonElement>('[aria-current="true"]');
                button?.focus({ preventScroll: true });
                button?.scrollIntoView({ block: "nearest" });
              }}
            >
              <IconArrowLeft aria-hidden="true" />
              返回阶段列表
            </Button>
            {selected && (
              <>
                <SpanAlerts
                  stageName={selected.span.stage_name}
                  status={selected.span.status}
                  payload={payload}
                />
                <StageMetricsBadges
                  stageName={selected.span.stage_name}
                  payload={{ ...payload, ...selected.typstMemory }}
                />
                <LlmAttemptsTable attempts={llmAttempts} />
                <RenderAttemptsTable attempts={renderAttempts} />
                {(selected.span.stage_name.toUpperCase() === "LLM_ANALYSIS" ||
                  Boolean(payload?.prompts)) && (
                  <PromptsInspector key={selected.span.span_id} prompts={payload?.prompts} />
                )}
                <SpanPayloadViewer payload={payload} />
                {(!payload || Object.keys(payload).length === 0) && (
                  <p className="stage-missing">此阶段没有额外记录。</p>
                )}
              </>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
