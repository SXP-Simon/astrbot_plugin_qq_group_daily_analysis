import type { TraceSpan } from "./types";

export interface SpanTreeNode {
  span: TraceSpan;
  children: SpanTreeNode[];
}

/** 将明确的父级关联组成树；缺失父级或循环关联回到顶层，避免丢失记录。 */
export function buildSpanTree(spans: TraceSpan[]): SpanTreeNode[] {
  const nodes = spans.map(span => ({ span, children: [] as SpanTreeNode[] }));
  const byId = new Map(nodes.map(node => [node.span.span_id, node]));
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
  return roots;
}


/** Child steps belong to their attempt and are not retries of another parent. */
export function spanGroupKey(span: TraceSpan): string {
  return typeof span.payload?.parent_span_id === "string" ? `span:${span.span_id}` : `stage:${span.stage_name}`;
}
