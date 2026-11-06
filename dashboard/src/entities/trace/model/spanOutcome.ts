export function resolveSpanOutcome(
  status: string,
  payload?: Record<string, unknown>,
): "cancelled" | "failed" | "warning" | "running" | "success" {
  if (["cancelled", "canceled", "aborted"].includes(status) || payload?.cancelled === true)
    return "cancelled";
  if (["failed", "error"].includes(status) || payload?.error) return "failed";
  if (status === "running") return "running";
  if (
    ["warning", "partial_success"].includes(status) ||
    payload?.success === false ||
    payload?.warning ||
    (Array.isArray(payload?.subtask_errors) && payload.subtask_errors.length)
  )
    return "warning";
  return "success";
}
