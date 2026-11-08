interface SpanPayloadViewerProps {
  payload?: Record<string, unknown>;
}

export function SpanPayloadViewer({ payload }: SpanPayloadViewerProps) {
  if (!payload || Object.keys(payload).length === 0) return null;

  return (
    <details className="mt-5 text-sm">
      <summary className="cursor-pointer rounded-md py-2 text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring">
        原始阶段记录（JSON）
      </summary>
      <pre className="m-0 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-muted p-3 font-mono text-xs leading-relaxed text-foreground">
        {JSON.stringify(payload, null, 2)}
      </pre>
    </details>
  );
}
