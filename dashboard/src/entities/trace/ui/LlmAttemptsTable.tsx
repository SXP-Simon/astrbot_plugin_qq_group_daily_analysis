import { ModelIcon } from "@/entities/config/ui/ModelIcon";
import { formatDuration } from "@/shared/lib/formatters";
import { llmAttemptSchema } from "@/entities/trace/model/llmAttempts";
import { resolveSpanOutcome } from "@/entities/trace/model/spanOutcome";

const areaNames = new Map(
  Object.entries({
    topics: "话题",
    user_titles: "用户称号",
    golden_quotes: "金句",
    chat_quality: "聊天质量",
    话题分析: "话题",
    群友画像: "用户称号",
    群聊金句: "金句",
    聊天质量: "聊天质量",
    group_sentiment: "情感分析",
    activity_prediction: "活跃预测",
    comic: "群漫画生成",
  }),
);
const statusLabels = {
  success: "成功",
  failed: "失败",
  cancelled: "已停止",
  running: "请求中",
  warning: "有警告",
  skipped: "已跳过",
  unknown: "状态未记录",
};

export function LlmAttemptsTable({ attempts }: { attempts: Record<string, unknown>[] }) {
  if (!attempts.length) return null;
  return (
    <section className="my-5 text-sm" aria-label="大模型调用与重试链路">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="m-0 text-sm font-medium">大模型调用与重试链路</h4>
        <span className="text-xs text-muted-foreground">共 {attempts.length} 条记录</span>
      </div>
      <ol className="m-0 list-none p-0">
        {attempts.map((record, index) => {
          const att = llmAttemptSchema.parse(record);
          const outcome = resolveSpanOutcome(att.status ?? "", { error: att.error });
          const retry = /^(.*)#(schema_retry|retry)_(\d+)$/.exec(att.area ?? "");
          const area = retry?.[1] ?? att.area;
          const provider = [
            att.provider_id,
            att.model && !att.provider_id?.includes(att.model) ? att.model : undefined,
          ]
            .filter(Boolean)
            .join(" / ");
          return (
            <li
              key={index}
              className="border-0 border-b border-solid border-border py-3 last:border-b-0"
            >
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="text-xs text-muted-foreground">记录 {index + 1}</span>
                <span className="flex-1 font-medium">
                  {area ? (areaNames.get(area) ?? area) : "分析模块未记录"}
                </span>
                <span
                  className={outcome === "failed" ? "text-destructive" : "text-muted-foreground"}
                >
                  {statusLabels[outcome]}
                </span>
                <span
                  className={`text-xs text-muted-foreground ${att.duration_ms === undefined ? "" : "font-mono"}`}
                >
                  {att.duration_ms === undefined
                    ? "耗时未记录"
                    : att.duration_ms === 0
                      ? "0ms"
                      : formatDuration(att.duration_ms)}
                </span>
              </div>
              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground">
                {provider && (
                  <span className="inline-flex min-w-0 items-center gap-2 font-mono">
                    <ModelIcon id={att.provider_id} model={att.model} className="size-4" />
                    <span className="min-w-0 break-all">{provider}</span>
                  </span>
                )}
                {att.attempt !== undefined && outcome !== "skipped" && (
                  <span>调用次数 {att.attempt}</span>
                )}
                {att.is_fallback && <span>备用 Provider</span>}
                {retry && (
                  <span>
                    {retry[2] === "schema_retry" ? "格式修复" : "重试"}第 {Number(retry[3])} 次
                  </span>
                )}
              </div>
              {att.skip_reason && (
                <p className="mb-0 mt-2 text-xs text-warning">未发送请求：{att.skip_reason}</p>
              )}
              {att.error && (
                <p
                  className={`mb-0 mt-2 whitespace-pre-wrap break-words font-mono text-xs ${outcome === "failed" ? "text-destructive" : "text-muted-foreground"}`}
                >
                  {att.error}
                </p>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
