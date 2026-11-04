import type { ReactNode } from "react";
import { MetricPill } from "../../../shared/ui/MetricPill";
import { useTheme } from "../../../shared/lib/useTheme";

export function RenderingStageMetrics({ payload, children }: { payload: Record<string, unknown>; children?: ReactNode }) {
  const { isDark } = useTheme();
  const ownProcessRss = ["linux_proc_status", "windows_working_set"].includes(String(payload.worker_rss_source));
  const native = payload.service_type === "typst";
  const phases: Record<string, string> = { font_setup: "字体初始化", layout: "布局测量", raster: "栅格导出" };
  const workerPhase = typeof payload.worker_phase === "string" ? phases[payload.worker_phase] : undefined;
  const memoryHints: Record<string, string> = {
    worker_start_rss_mb: "子进程加载编译器前的 RSS，作为本次编译内存增长的基准。",
    worker_peak_rss_mb: "隔离进程自身的峰值常驻内存，进程退出后释放，不计入宿主 RSS 净变化。",
    worker_peak_delta_mb: "子进程峰值减去启动 RSS，表示本次编译的峰值增长，不是结束后的内存泄漏量。",
  };
  const metrics = [
    ["strategy_name", "方案", ""],
    ["service_type", "引擎", ""],
    ["font_mode", "字体来源", ""],
    ["title_font", "标题字体", ""],
    ["resource_environment", "资源环境", ""],
    ["execution_location", "执行位置", ""],
    ["asset_policy", "素材获取", ""],
    ["viewport", "视口", ""],
    ["width", "固定宽度", "px"],
    ["requested_raster_ppi", "请求密度", "PPI"],
    ["raster_ppi", "实际导出密度", "PPI"],
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
    ["worker_start_rss_mb", "子进程启动 RSS", "MiB"],
    ["worker_peak_rss_mb", "子进程 RSS 峰值", "MiB"],
    ["worker_peak_delta_mb", "编译峰值增长", "MiB"],
    ["image_bytes", "图片字节", "B"],
  ] as const;
  return (
    <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 6 }}>
      {metrics.map(([key, label, unit]) => {
        if (native && key === "resource_environment") return null;
        const value = payload[key];
        if (unit === "" ? typeof value !== "string" || !value.trim() : typeof value !== "number" || !Number.isFinite(value) || value < 0) return null;
        const metricLabel = key === "worker_peak_rss_mb" && !ownProcessRss ? "进程历史 RSS 峰值" : label;
        const hint = key === "worker_peak_rss_mb" && !ownProcessRss ? "进程历史峰值可能包含启动时继承的内存，不等于本次隔离编译占用。" : memoryHints[key];
        return <span key={key} title={hint}><MetricPill isDark={isDark} label={metricLabel} value={`${typeof value === "number" ? value.toLocaleString() : String(value)} ${unit}`} status={key.startsWith("missing_") && typeof value === "number" && value > 0 ? "warning" : "default"} /></span>;
      })}
      {payload.network_budget_exhausted === true && <MetricPill isDark={isDark} label="网络预算" value="已耗尽，保留正文" status="warning" isMono={false} />}
      {payload.mode === "basic" && <MetricPill isDark={isDark} label="恢复方案" value="基础排版" isMono={false} />}
      {workerPhase && <MetricPill isDark={isDark} label="最后阶段" value={workerPhase} status="warning" isMono={false} />}
      {payload.worker_metrics_partial === true && <span style={{ flexBasis: "100%", fontSize: 11 }}>指标为进程终止前的采样，未完成的阶段不显示完整耗时。</span>}
      {payload.mode === "basic" && typeof payload.original_raster_ppi === "number" && typeof payload.requested_raster_ppi === "number" && payload.original_raster_ppi > payload.requested_raster_ppi && <span style={{ flexBasis: "100%", fontSize: 11 }}>基础恢复使用标准密度 {payload.requested_raster_ppi} PPI。</span>}
      {typeof payload.raster_ppi === "number" && typeof payload.requested_raster_ppi === "number" && payload.raster_ppi < payload.requested_raster_ppi && <span style={{ flexBasis: "100%", fontSize: 11 }}>长图像素预算已限制导出密度，排版与内容保持不变。</span>}
      {children}
      {typeof payload.worker_peak_rss_mb === "number" && Number.isFinite(payload.worker_peak_rss_mb) && payload.worker_peak_rss_mb >= 0 && <span style={{ flexBasis: "100%", fontSize: 11, color: isDark ? "#8b949e" : "#64748b" }}>
        {ownProcessRss ? "宿主净变化不含隔离编译开销；子进程结束后释放内存。" : "历史采集口径可能包含启动时继承的内存，不能直接作为本次编译占用。"}
      </span>}
    </div>
  );
}
