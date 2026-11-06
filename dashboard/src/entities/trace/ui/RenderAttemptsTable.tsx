import { formatDuration } from "../../../shared/lib/formatters";
import { renderAttemptSchema } from "../model/renderAttempts";
import { resolveSpanOutcome } from "../model/spanOutcome";

const serviceNames = { astrbot: "AstrBot T2I", custom: "自定义 T2I", typst: "Typst 本地排版" };
const statusLabels = {
  success: "渲染成功",
  failed: "渲染失败",
  cancelled: "已停止",
  running: "正在渲染",
  warning: "有警告",
  skipped: "已跳过",
  unknown: "状态未知",
};

export function RenderAttemptsTable({ attempts }: { attempts: Record<string, unknown>[] }) {
  if (!attempts.length) return null;
  return (
    <section className="my-5 text-sm" aria-label="图片渲染过程">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="m-0 text-sm font-medium">图片渲染过程</h4>
        <span className="text-xs text-muted-foreground">共 {attempts.length} 轮策略</span>
      </div>
      <ol className="m-0 list-none p-0">
        {attempts.map((record, index) => {
          const att = renderAttemptSchema.parse(record);
          const outcome = resolveSpanOutcome(att.status ?? "", { error: att.error });
          const typst = att.service_type === "typst";
          const font = typst
            ? "插件数据目录字体"
            : att.font_mode === "local"
              ? "本地已安装字体"
              : att.font_mode === "network"
                ? "在线字体"
                : undefined;
          const details = [
            att.priority != null ? `优先级 ${att.priority}` : undefined,
            att.service_type ? serviceNames[att.service_type] : undefined,
            att.type ? `格式：${att.type}` : undefined,
            !typst && att.resource_environment
              ? `资源环境：${att.resource_environment === "Mainland" ? "内地" : att.resource_environment === "Overseas" ? "海外" : att.resource_environment}`
              : undefined,
            font ? `字体：${font}` : undefined,
            att.viewport ? `视口：${att.viewport}` : undefined,
            att.render_timeout_ms != null
              ? `${typst ? "单次编译上限" : "渲染超时"}：${att.render_timeout_ms === 0 ? "0ms" : formatDuration(att.render_timeout_ms)}`
              : undefined,
            att.request_timeout_ms != null
              ? `请求等待上限：${att.request_timeout_ms === 0 ? "0ms" : formatDuration(att.request_timeout_ms)}`
              : undefined,
          ].filter((value) => value !== undefined);
          const addresses = [
            ["服务", att.render_service?.configured_endpoint],
            ["配置来源", att.render_service?.config_lookup],
            ["模板资源", att.resource_urls?.cdn_base_url],
            ...(!typst && att.font_mode !== "local"
              ? [
                  ["字体 CSS", att.resource_urls?.google_fonts],
                  ["字体文件", att.resource_urls?.gstatic],
                ]
              : []),
          ].filter(([, value]) => Boolean(value));
          return (
            <li
              key={index}
              className="border-0 border-b border-solid border-border py-3 last:border-b-0"
            >
              <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                <span className="text-xs text-muted-foreground">
                  第 {att.attempt ?? index + 1} 轮
                </span>
                <span className="flex-1 font-medium">{att.strategy_name ?? "渲染方案"}</span>
                <span
                  className={outcome === "failed" ? "text-destructive" : "text-muted-foreground"}
                >
                  {statusLabels[outcome]}
                </span>
                <span className="font-mono text-xs text-muted-foreground">
                  {att.duration_ms === undefined
                    ? "耗时未记录"
                    : `耗时：${att.duration_ms === 0 ? "0ms" : formatDuration(att.duration_ms)}`}
                </span>
              </div>
              {details.length > 0 && (
                <ul className="mb-0 mt-2 grid list-none grid-cols-1 gap-x-4 gap-y-1 p-0 text-xs text-muted-foreground sm:grid-cols-2">
                  {details.map((value) => (
                    <li key={value}>{value}</li>
                  ))}
                </ul>
              )}
              {att.error && (
                <p
                  className={`mb-0 mt-2 whitespace-pre-wrap break-words font-mono text-xs ${outcome === "failed" ? "text-destructive" : "text-muted-foreground"}`}
                >
                  {att.error}
                </p>
              )}
              {addresses.length > 0 && (
                <details className="mt-2 text-xs">
                  <summary className="cursor-pointer rounded-md py-1 text-muted-foreground focus-visible:outline-2 focus-visible:outline-ring">
                    服务与素材地址
                  </summary>
                  <div className="mt-1 space-y-1 break-all font-mono text-muted-foreground">
                    {addresses.map(([label, value]) => (
                      <div key={label}>
                        {label}：{value}
                      </div>
                    ))}
                  </div>
                </details>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
