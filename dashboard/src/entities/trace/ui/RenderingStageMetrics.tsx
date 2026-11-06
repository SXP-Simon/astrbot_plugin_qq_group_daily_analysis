import type { ReactNode } from "react";
import { StageMetric } from "./StageMetric";

export function RenderingStageMetrics({
  payload,
  children,
}: {
  payload: Record<string, unknown>;
  children?: ReactNode;
}) {
  const ownProcessRss = ["linux_proc_status", "windows_working_set"].includes(
    String(payload.worker_rss_source),
  );
  const ownTypstRss = ["linux_proc_status", "windows_working_set"].includes(
    String(payload.typst_rss_source),
  );
  const native = payload.service_type === "typst";
  const phases: Record<string, string> = {
    font_setup: "字体初始化",
    layout: "布局测量",
    raster: "栅格导出",
  };
  const workerPhase =
    typeof payload.worker_phase === "string" ? phases[payload.worker_phase] : undefined;
  const metricHints: Record<string, string> = {
    raster_cpu_ms:
      "隔离进程在栅格阶段实际消耗的 CPU 时间，包含线程累计，可能超过墙钟时间；较大等待差距还需结合调度、配额或磁盘情况判断。",
    worker_cpu_ms: "本次隔离编译实际消耗的 CPU 时间，不包含进程未获调度的等待。",
    cpu_quota_cores:
      "从常见容器 cgroup 挂载根读取的 CPU 配额，不代表实时可用核数；可能另受上级配额、cpuset 或主机竞争限制。未显示不代表无限制。",
    worker_start_rss_mb: "子进程加载编译器前的 RSS，作为本次编译内存增长的基准。",
    worker_peak_rss_mb: "隔离进程自身的峰值常驻内存，进程退出后释放，不计入宿主 RSS 净变化。",
    worker_peak_delta_mb:
      "子进程峰值减去启动 RSS，表示本次编译的峰值增长，不是结束后的内存泄漏量。",
    typst_peak_rss_mb:
      "取本阶段内各次串行 Typst 编译的最大 RSS 峰值，不相加，也不等于宿主内存增长。",
    typst_peak_delta_mb:
      "取各次 Typst 编译相对其自身启动 RSS 的最大增长量；与宿主 RSS 净变化分开记录。",
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
    ["raster_cpu_ms", "栅格 CPU 耗时", "ms"],
    ["worker_cpu_ms", "编译 CPU 耗时", "ms"],
    ["cpu_quota_cores", "容器 CPU 配额", "核"],
    ["worker_start_rss_mb", "子进程启动 RSS", "MiB"],
    ["worker_peak_rss_mb", "子进程 RSS 峰值", "MiB"],
    ["worker_peak_delta_mb", "编译峰值增长", "MiB"],
    ["typst_peak_rss_mb", "Typst 子进程 RSS 峰值", "MiB"],
    ["typst_peak_delta_mb", "Typst 编译峰值增长", "MiB"],
    ["image_bytes", "图片字节", "B"],
  ] as const;
  return (
    <div className="stage-metrics-grid">
      {metrics.map(([key, label, unit]) => {
        if (native && key === "resource_environment") return null;
        const value = payload[key];
        if (
          unit === ""
            ? typeof value !== "string" || !value.trim()
            : typeof value !== "number" || !Number.isFinite(value) || value < 0
        )
          return null;
        const metricLabel =
          key === "worker_peak_rss_mb" && !ownProcessRss
            ? "进程历史 RSS 峰值"
            : key === "typst_peak_rss_mb" && !ownTypstRss
              ? "Typst 历史口径 RSS 峰值"
              : label;
        const hint =
          key === "worker_peak_rss_mb" && !ownProcessRss
            ? "进程历史峰值可能包含启动时继承的内存，不等于本次隔离编译占用。"
            : metricHints[key];
        return (
          <span key={key} title={hint}>
            <StageMetric
              label={metricLabel}
              value={`${typeof value === "number" ? value.toLocaleString() : String(value)} ${unit}`}
              status={
                key.startsWith("missing_") && typeof value === "number" && value > 0
                  ? "warning"
                  : "default"
              }
            />
          </span>
        );
      })}
      {payload.network_budget_exhausted === true && (
        <StageMetric label="网络预算" value="已耗尽，保留正文" status="warning" isMono={false} />
      )}
      {payload.mode === "basic" && <StageMetric label="恢复方案" value="基础排版" isMono={false} />}
      {workerPhase && (
        <StageMetric label="最后阶段" value={workerPhase} status="warning" isMono={false} />
      )}
      {payload.worker_metrics_partial === true && (
        <span className="col-span-full text-xs text-muted-foreground">
          指标为进程终止前的采样，未完成的阶段不显示完整耗时。
        </span>
      )}
      {payload.typst_metrics_partial === true && (
        <span className="col-span-full text-xs text-muted-foreground">
          Typst 汇总包含中断前的采样；各次串行编译取最大值，不相加。
        </span>
      )}
      {payload.mode === "basic" &&
        typeof payload.original_raster_ppi === "number" &&
        typeof payload.requested_raster_ppi === "number" &&
        payload.original_raster_ppi > payload.requested_raster_ppi && (
          <span className="col-span-full text-xs text-muted-foreground">
            基础恢复使用标准密度 {payload.requested_raster_ppi} PPI。
          </span>
        )}
      {typeof payload.raster_ppi === "number" &&
        typeof payload.requested_raster_ppi === "number" &&
        payload.raster_ppi < payload.requested_raster_ppi && (
          <span className="col-span-full text-xs text-muted-foreground">
            长图像素预算已限制导出密度，排版与内容保持不变。
          </span>
        )}
      {children}
      {typeof payload.worker_peak_rss_mb === "number" &&
        Number.isFinite(payload.worker_peak_rss_mb) &&
        payload.worker_peak_rss_mb >= 0 && (
          <span className="col-span-full text-xs text-muted-foreground">
            {ownProcessRss
              ? "宿主净变化不含隔离编译开销；子进程结束后释放内存。"
              : "历史采集口径可能包含启动时继承的内存，不能直接作为本次编译占用。"}
          </span>
        )}
    </div>
  );
}
