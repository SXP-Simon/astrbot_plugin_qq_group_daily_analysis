import type { ContextMetrics } from "../../entities/trace/model/types";

interface ContextFunnelWidgetProps {
  metrics: Partial<ContextMetrics>;
}

const count = (value: number | null | undefined) =>
  typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : null;

export function ContextFunnelWidget({ metrics }: ContextFunnelWidgetProps) {
  const raw = count(metrics.raw_message_count);
  const cleaned = count(metrics.cleaned_message_count);
  const inconsistent = raw !== null && cleaned !== null && cleaned > raw;
  const removed = raw !== null && cleaned !== null && !inconsistent ? raw - cleaned : null;
  const ratio = count(metrics.compression_ratio);
  const retention = ratio !== null && ratio <= 1 ? ratio * 100 : null;
  const values = [
    { label: "读取消息", value: raw, unit: "条" },
    { label: "有效消息", value: cleaned, unit: "条" },
    { label: "过滤消息", value: removed, unit: "条" },
    { label: "增量批次", value: count(metrics.incremental_batches), unit: "批" },
    { label: "采样窗口", value: count(metrics.window_size), unit: "条" },
  ];
  return (
    <section aria-label="消息留存" className="min-w-0 space-y-5">
      <h2 className="m-0 text-lg font-medium">消息留存</h2>
      <div className="space-y-2">
        <div className="flex flex-wrap items-baseline justify-between gap-2 text-sm">
          <span className="text-muted-foreground">有效消息占读取消息</span>
          <span className="font-mono text-lg">
            {retention === null ? "未记录" : `${Number(retention.toFixed(1))}%`}
          </span>
        </div>
        {retention !== null && (
          <div aria-hidden="true" className="h-2 overflow-hidden rounded-full bg-muted">
            <div className="h-full rounded-full bg-primary" style={{ width: `${retention}%` }} />
          </div>
        )}
      </div>
      <dl className="m-0 divide-y divide-border">
        {values.map(({ label, value, unit }) => (
          <div key={label} className="flex flex-wrap items-baseline justify-between gap-2 py-3">
            <dt className="text-sm text-muted-foreground">{label}</dt>
            <dd className="m-0 font-mono">
              {value === null ? "未记录" : `${value.toLocaleString()} ${unit}`}
            </dd>
          </div>
        ))}
      </dl>
      {inconsistent && (
        <p className="m-0 text-sm text-destructive">
          有效消息多于读取消息，记录不一致，无法计算过滤数量。
        </p>
      )}
    </section>
  );
}
