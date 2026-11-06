import { resolveSpanOutcome } from "../model/spanOutcome";
import { getRenderAttemptDiagnostic } from "../model/renderAttempts";

interface SpanAlertsProps {
  stageName: string;
  status: string;
  payload?: Record<string, unknown>;
}

export function SpanAlerts({ stageName, status, payload }: SpanAlertsProps) {
  const outcome = resolveSpanOutcome(status, payload);
  const messages: { label: string; value: unknown; danger?: boolean }[] = [];
  const renderDiagnostic = getRenderAttemptDiagnostic(payload);
  if (renderDiagnostic)
    messages.push({
      label: renderDiagnostic.label,
      value: `此前失败原因：${renderDiagnostic.reason}`,
    });
  if (outcome === "cancelled") messages.push({ label: "已停止", value: "该阶段已停止。" });
  if (payload?.failure_reason)
    messages.push({ label: "原始失败原因", value: payload.failure_reason });
  if (payload?.mode === "basic" && payload.reason)
    messages.push({ label: "恢复原因", value: payload.reason });
  if (outcome === "failed")
    messages.push({
      label: "阶段执行异常",
      value: payload?.error || "该阶段执行失败，未记录具体原因。",
      danger: true,
    });
  if (outcome !== "failed" && payload?.warning)
    messages.push({ label: "阶段警告", value: payload.warning });
  if (Array.isArray(payload?.subtask_errors)) {
    for (const error of payload.subtask_errors) {
      if (error != null && error !== "") messages.push({ label: "子任务异常", value: error });
    }
  }
  if (
    stageName.toUpperCase() === "LLM_ANALYSIS" &&
    ["success", "warning", "skipped"].includes(outcome)
  ) {
    const features = payload?.enabled_features;
    const flags = new Map<string, unknown>(
      Object.entries(
        features && typeof features === "object" && !Array.isArray(features) ? features : {},
      ),
    );
    const knownFlags = ["topics", "user_titles", "golden_quotes", "chat_quality"].map((key) =>
      flags.get(key),
    );
    if (knownFlags.every((flag) => flag === false)) {
      messages.push({ label: "未启用分析模块", value: "话题、群友画像、金句和质量锐评均未开启。" });
    } else if (
      knownFlags.some((flag) => flag === true) &&
      payload?.topics_count === 0 &&
      payload.user_titles_count === 0 &&
      payload.golden_quotes_count === 0 &&
      payload.chat_quality_review === false
    ) {
      messages.push({
        label: "未记录分析结果",
        value: "本阶段记录的话题、画像、金句和质量锐评均为空，可展开提示词与模型返回查看。",
      });
    }
  }
  if (!messages.length) return null;
  return (
    <div className="mb-4 space-y-3 text-sm" aria-label="阶段提示">
      {messages.map(({ label, value, danger }, index) => (
        <div
          key={index}
          className={`border-0 border-l-2 border-solid pl-3 ${danger ? "border-destructive text-destructive" : "border-border text-foreground"}`}
        >
          <p className="m-0 font-medium">{label}</p>
          <p className="mb-0 mt-1 whitespace-pre-wrap break-words font-mono text-xs leading-relaxed">
            {typeof value === "string" ? value : JSON.stringify(value)}
          </p>
        </div>
      ))}
    </div>
  );
}
