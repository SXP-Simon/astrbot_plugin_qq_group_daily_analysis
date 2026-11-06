import type { TraceSpan } from "./types";

export interface SpanTreeNode {
  span: TraceSpan;
  children: SpanTreeNode[];
  typstMemory?: TypstMemorySummary;
}

interface TypstMemorySummary {
  typst_peak_rss_mb?: number;
  typst_peak_delta_mb?: number;
  typst_rss_source?: string;
  typst_metrics_partial?: boolean;
}

/** 将明确的父级关联组成树；缺失父级或循环关联回到顶层，避免丢失记录。 */
export function buildSpanTree(spans: TraceSpan[]): SpanTreeNode[] {
  const nodes: SpanTreeNode[] = spans.map((span) => ({ span, children: [] }));
  const byId = new Map(nodes.map((node) => [node.span.span_id, node]));
  const roots: SpanTreeNode[] = [];
  for (const node of nodes) {
    const parentId = node.span.payload?.parent_span_id;
    let parent = typeof parentId === "string" ? byId.get(parentId) : undefined;
    let ancestor = parent;
    const visited = new Set([node.span.span_id]);
    while (ancestor) {
      if (visited.has(ancestor.span.span_id)) {
        parent = undefined;
        break;
      }
      visited.add(ancestor.span.span_id);
      const ancestorId = ancestor.span.payload?.parent_span_id;
      ancestor = typeof ancestorId === "string" ? byId.get(ancestorId) : undefined;
    }
    if (parent) parent.children.push(node);
    else roots.push(node);
  }
  roots.forEach(summarizeTypstMemory);
  return roots;
}

/** 从子阶段补齐旧记录的编译内存汇总，不修改原始 Payload 或宿主 RSS。 */
function summarizeTypstMemory(node: SpanTreeNode): TypstMemorySummary {
  const summary: TypstMemorySummary = {};
  const payload = node.span.payload || {};
  const compiler = ["TYPST_COMPILE", "TYPST_RECOVERY"].includes(node.span.stage_name);
  const peak = compiler ? payload.worker_peak_rss_mb : payload.typst_peak_rss_mb;
  const delta = compiler ? payload.worker_peak_delta_mb : payload.typst_peak_delta_mb;
  const source = compiler ? payload.worker_rss_source : payload.typst_rss_source;
  if (typeof peak === "number" && Number.isFinite(peak) && peak >= 0) {
    summary.typst_peak_rss_mb = peak;
    summary.typst_rss_source = typeof source === "string" ? source : "unknown";
  }
  if (typeof delta === "number" && Number.isFinite(delta) && delta >= 0)
    summary.typst_peak_delta_mb = delta;
  if (payload.worker_metrics_partial === true || payload.typst_metrics_partial === true)
    summary.typst_metrics_partial = true;
  for (const child of node.children) {
    const memory = summarizeTypstMemory(child);
    if (
      memory.typst_peak_rss_mb !== undefined &&
      memory.typst_peak_rss_mb >= (summary.typst_peak_rss_mb ?? -1)
    ) {
      summary.typst_peak_rss_mb = memory.typst_peak_rss_mb;
      summary.typst_rss_source = memory.typst_rss_source;
    }
    if (memory.typst_peak_delta_mb !== undefined)
      summary.typst_peak_delta_mb = Math.max(
        summary.typst_peak_delta_mb ?? 0,
        memory.typst_peak_delta_mb,
      );
    if (memory.typst_metrics_partial) summary.typst_metrics_partial = true;
  }
  if (["RENDER_REPORT", "REPORT_RENDERING", "IMAGE_RENDER_ATTEMPT"].includes(node.span.stage_name))
    node.typstMemory = summary;
  return summary;
}

/** 子步骤归属于当前尝试，不与其他父阶段合并为重试。 */
export function spanGroupKey(span: TraceSpan): string {
  return typeof span.payload?.parent_span_id === "string"
    ? `span:${span.span_id}`
    : `stage:${span.stage_name}`;
}
