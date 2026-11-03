import type { ReactNode } from "react";
import { MetricPill } from "../../../shared/ui/MetricPill";
import { useTheme } from "../../../shared/lib/useTheme";

export function RenderingStageMetrics({ payload, children }: { payload: Record<string, unknown>; children?: ReactNode }) {
  const { isDark } = useTheme();
  const metrics = [
    ["strategy_name", "方案", ""],
    ["service_type", "引擎", ""],
    ["font_mode", "字体来源", ""],
    ["resource_environment", "资源环境", ""],
    ["viewport", "视口", ""],
    ["width", "固定宽度", "px"],
    ["topics", "话题", "项"],
    ["portraits", "画像", "项"],
    ["quotes", "金句", "项"],
    ["local_resources", "本地原素材复用", "次"],
    ["image_cache_hits", "图片缓存复用", "次"],
    ["downloaded_resources", "本次下载", "个"],
    ["missing_resources", "占位图标", "个"],
    ["missing_images", "缺失图片来源", "个"],
    ["font_setup_ms", "字体初始化", "ms"],
    ["layout_ms", "布局测量", "ms"],
    ["raster_ms", "栅格导出", "ms"],
    ["worker_peak_rss_mb", "编译进程峰值", "MiB"],
    ["image_bytes", "图片字节", "B"],
  ] as const;
  return (
    <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
      {metrics.map(([key, label, unit]) => {
        const value = payload[key];
        if (unit === "" ? typeof value !== "string" || !value.trim() : typeof value !== "number" || !Number.isFinite(value) || value < 0) return null;
        return <MetricPill key={key} isDark={isDark} label={label} value={`${typeof value === "number" ? value.toLocaleString() : String(value)} ${unit}`} status={key.startsWith("missing_") && typeof value === "number" && value > 0 ? "warning" : "default"} />;
      })}
      {payload.network_budget_exhausted === true && <MetricPill isDark={isDark} label="网络预算" value="已耗尽，保留正文" status="warning" isMono={false} />}
      {payload.mode === "basic" && <MetricPill isDark={isDark} label="恢复方案" value="基础排版" isMono={false} />}
      {children}
    </div>
  );
}
