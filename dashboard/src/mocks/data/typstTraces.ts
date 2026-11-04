import type { TraceRecord, TraceSpan } from "../../entities/trace/model/types";

interface Step {
  stage: string;
  ms?: number;
  status?: string;
  payload?: Record<string, unknown>;
  children?: Step[];
}
interface Scene {
  id: string;
  name: string;
  status: "succeeded" | "running" | "warning" | "failed" | "aborted";
  recovered?: boolean;
  fallback?: boolean;
  validation?: "fonts" | "theme";
  htmlFirst?: boolean;
  theme?: string;
  titleFontMissing?: boolean;
}
const scenes: Scene[] = [
  { id: "cached", name: "本地素材命中", status: "succeeded" },
  { id: "title-font", name: "缺全瀨體时标题回退", status: "warning", titleFontMissing: true },
  { id: "live", name: "CDN 下载中", status: "running" },
  { id: "network", name: "资源超时仍完成", status: "warning" },
  { id: "recovered", name: "基础排版恢复", status: "warning", recovered: true },
  { id: "failed", name: "编译与恢复均失败", status: "failed", recovered: true },
  { id: "cancelled", name: "编译阶段取消", status: "aborted" },
  { id: "fonts", name: "缺字体后 HTML 回退", status: "warning", validation: "fonts", fallback: true },
  { id: "theme", name: "仅 HTML 主题回退", status: "warning", validation: "theme", fallback: true, theme: "custom_hacker" },
  { id: "fallback", name: "原生恢复失败后 HTML 回退", status: "warning", recovered: true, fallback: true },
  { id: "html-native", name: "无 HTML 入口后原生恢复", status: "warning", htmlFirst: true, theme: "custom_native" },
];

const workerMetrics = { raster_ppi: 144, requested_raster_ppi: 144, font_setup_ms: 85, layout_ms: 190, raster_ms: 670, worker_start_rss_mb: 11.7, worker_peak_rss_mb: 156.9, worker_peak_delta_mb: 145.2, worker_rss_source: "linux_proc_status" };
const restored = { warning: "后续渲染方案已恢复图片报告" };

function nativeSteps(scene: Scene): Step[] {
  const theme = scene.theme || "HatsuneMiku";
  const reason = scene.validation === "fonts" ? "请先在 WebUI 下载 Typst 字体到插件数据目录" : "该主题没有 report.typ，请选择支持 Typst 的主题或 HTML 渲染方案";
  if (scene.validation) return [{ stage: "TYPST_VALIDATE", ms: 3, status: "warning", payload: { template: theme, width: 940, failure_reason: reason, ...restored } }];
  const resourceTimeout = scene.id === "network";
  const steps: Step[] = [
    { stage: "TYPST_VALIDATE", ms: 3, payload: { template: theme, width: 940 } },
    { stage: "TYPST_DATA", ms: 120, payload: { topics: 3, portraits: 4, quotes: 2 } },
    { stage: "TYPST_RESOURCES", ms: resourceTimeout ? 19800 : scene.id === "live" ? 7797 : 60, status: scene.id === "live" ? "running" : "success", payload: {
      ...(theme === "HatsuneMiku" ? { title_font: scene.titleFontMissing ? "Noto Sans SC" : "cjkFonts" } : {}),
      ...(scene.titleFontMissing ? { warning: "全瀨體尚未下载，中文标题暂用 Noto；可在 WebUI 补齐 Miku 模板字体" } : {}),
      local_resources: scene.id === "cached" ? 10 : 2, image_cache_hits: scene.id === "cached" ? 9 : 0,
      downloaded_resources: scene.id === "live" ? 4 : 0, missing_resources: resourceTimeout ? 2 : 0,
      missing_images: resourceTimeout ? 1 : 0, network_budget_exhausted: resourceTimeout,
      ...(resourceTimeout ? { warning: "部分素材请求超时，保留正文继续排版；可在配置中心下载主题素材或切换 CDN" } : {}),
    } },
  ];
  if (scene.status === "running") return steps;
  const compileFailed = scene.recovered;
  steps.push({ stage: "TYPST_COMPILE", ms: compileFailed ? 310 : scene.id === "cached" ? 1752 : 945,
    status: scene.status === "aborted" ? "cancelled" : compileFailed ? scene.status === "failed" ? "failed" : "warning" : "success",
    payload: { template: theme, width: 940, ...(scene.status === "aborted" ? {} : compileFailed ? { font_setup_ms: 85, layout_ms: 190, worker_start_rss_mb: 12, worker_peak_rss_mb: 103.5, worker_peak_delta_mb: 91.5, worker_rss_source: "linux_proc_status" } : { ...workerMetrics, ...(scene.id === "cached" ? { requested_raster_ppi: 216, raster_ppi: 216, font_setup_ms: 25.74, layout_ms: 109.57, raster_ms: 1616, worker_start_rss_mb: 20.61, worker_peak_rss_mb: 222.07, worker_peak_delta_mb: 201.46 } : scene.id === "network" ? { requested_raster_ppi: 216, raster_ppi: 180 } : {}) }),
      ...(compileFailed ? scene.status === "failed" ? { error: "主题第 18 行：预期长度，得到字符串" } : { failure_reason: "主题第 18 行：预期长度，得到字符串", warning: scene.fallback ? restored.warning : "主题编译失败，基础排版已恢复完整报告" } : {}),
      ...(scene.status === "aborted" ? { cancelled: true } : {}),
    } });
  if (scene.recovered) steps.push({ stage: "TYPST_RECOVERY", ms: 530,
    status: scene.status === "failed" ? "failed" : scene.fallback ? "warning" : "success",
    payload: { mode: "basic", reason: "主题类型错误", font_setup_ms: 82, layout_ms: 65, requested_raster_ppi: 144, raster_ppi: 144, worker_start_rss_mb: 11.8, worker_peak_rss_mb: 119.3, worker_peak_delta_mb: 107.5, worker_rss_source: "linux_proc_status", ...(!scene.fallback && scene.status !== "failed" ? { raster_ms: 380 } : {}),
      ...(scene.status === "failed" ? { error: "基础恢复也超出本轮编译预算" } : scene.fallback ? { failure_reason: "基础排版编译失败", ...restored } : {}),
    } });
  if (!scene.fallback && scene.status !== "failed" && scene.status !== "aborted") steps.push({ stage: "TYPST_ENCODE", ms: 9, payload: { format: "png", image_bytes: 382910 } });
  return steps;
}

/** Flatten a small recipe tree while keeping parent timing inclusive. */
function appendSteps(steps: Step[], traceId: string, started: number, spans: TraceSpan[], parent?: string, offset = 0): number {
  let elapsed = offset;
  for (const step of steps) {
    const id = `${traceId}-${spans.length}-${step.stage}`;
    const start = elapsed;
    const status = step.status || "success";
    const span: TraceSpan = { span_id: id, trace_id: traceId, stage_name: step.stage, status,
      started_at: started + start / 1000, duration_ms: null,
      start_memory_mb: 88.2, end_memory_mb: status === "running" ? null : 88.6,
      delta_memory_mb: status === "running" ? null : 0.4,
      payload: { ...step.payload, ...(parent ? { parent_span_id: parent } : {}) },
    };
    spans.push(span);
    elapsed = step.children ? appendSteps(step.children, traceId, started, spans, id, elapsed) : elapsed + (step.ms || 0);
    span.duration_ms = status === "running" ? null : elapsed - start;
  }
  return elapsed;
}

export const mockTypstTraces: TraceRecord[] = scenes.map((scene, index) => {
  const traceId = `trace-typst-${scene.id}`;
  const theme = scene.theme || "HatsuneMiku";
  const started = Date.now() / 1000 - (scene.status === "running" ? 8 : 90 + index * 60);
  const attempts: Step[] = [];
  if (scene.htmlFirst) attempts.push({ stage: "IMAGE_RENDER_ATTEMPT", status: "warning", payload: { attempt: 1, service_type: "astrbot", strategy_name: "HTML 优先方案", failure_reason: "主题没有 HTML 图片入口", ...restored }, children: [
    { stage: "IMAGE_HTML_PREPARE", ms: 40, status: "warning", payload: { failure_reason: "该主题只有 report.typ，没有 image_template.html", ...restored } },
  ] });
  attempts.push({ stage: "IMAGE_RENDER_ATTEMPT", status: scene.fallback ? "warning" : scene.status === "running" ? "running" : scene.status === "failed" ? "failed" : scene.status === "aborted" ? "cancelled" : "success",
    payload: { attempt: attempts.length + 1, service_type: "typst", strategy_name: "Typst 本地方案", ...(scene.fallback ? restored : {}) }, children: nativeSteps(scene) });
  if (scene.fallback) attempts.push({ stage: "IMAGE_RENDER_ATTEMPT", payload: { attempt: 2, service_type: "astrbot", strategy_name: "HTML 后备方案" }, children: [
    { stage: "IMAGE_HTML_PREPARE", ms: 180, payload: { template: theme, resource_environment: "Mainland" } },
    { stage: "IMAGE_SERVICE_RENDER", ms: 940, payload: { service_type: "astrbot", viewport: "940x900" } },
  ] });
  const records = attempts.map((attempt, i) => ({ attempt: i + 1, strategy_name: attempt.payload?.strategy_name, service_type: attempt.payload?.service_type,
    status: attempt.status === "warning" ? "failed" : attempt.status || "success", font_mode: attempt.payload?.service_type === "typst" ? "local" : "network",
    type: "png", render_timeout_ms: 30000, viewport: attempt.payload?.service_type === "typst" ? "Typst 固定 940px" : "940x900", started_at: started + .11,
    ...(attempt.status === "warning" ? { error: scene.validation ? "原生模板或字体检查未通过" : "本轮渲染失败，后续方案已恢复" } : {}),
  }));
  const steps: Step[] = [{ stage: "CHECKPOINT_RESTORE", ms: 80, payload: { resumed_from: "mock-report-checkpoint" } }, {
    stage: "RENDER_REPORT", status: scene.status === "running" ? "running" : scene.status === "failed" ? "failed" : scene.status === "aborted" ? "cancelled" : "success",
    payload: { template: theme, format: "image", render_attempts: records, ...(scene.status === "succeeded" || scene.status === "warning" ? { image_bytes: 382910, dimensions: scene.id === "cached" ? "1410x4875" : scene.id === "network" ? "1175x25000" : "940x3250", image_format: "png", render_attempt: records.length } : {}) },
    children: [{ stage: "IMAGE_RENDER_QUEUE", ms: 30 }, ...attempts],
  }];
  if (scene.status === "succeeded" || scene.status === "warning") steps.push({ stage: "DISPATCH_REPORT", ms: 280, payload: { platform: "aiocqhttp", formats: ["image"], success: true } });
  const spans: TraceSpan[] = [];
  const elapsed = appendSteps(steps, traceId, started, spans);
  const attemptSpans = spans.filter(span => span.stage_name === "IMAGE_RENDER_ATTEMPT");
  records.forEach((record, i) => Object.assign(record, { started_at: attemptSpans[i].started_at, duration_ms: attemptSpans[i].duration_ms }));
  return { trace_id: traceId, group_id: `typst-demo-${index}`, group_name: `Typst · ${scene.name}`,
    platform: "aiocqhttp", trigger_type: "web_ui", status: scene.status,
    started_at: started, completed_at: scene.status === "running" ? null : started + elapsed / 1000,
    duration_ms: scene.status === "running" ? null : elapsed, current_stage: spans[spans.length - 1].stage_name, spans,
    error_stage: scene.status === "failed" ? "TYPST_RECOVERY" : scene.status === "aborted" ? "TYPST_COMPILE" : null,
    error_message: scene.status === "failed" ? "所有配置的渲染方案均失败" : scene.status === "aborted" ? "用户主动中止任务" : null,
    performance_metrics: { trace_id: traceId, init_memory_mb: 88.2, peak_memory_mb: 89.4, final_memory_mb: 88.8, delta_memory_mb: 0.6 },
    extra: scene.status === "warning" ? { has_warnings: true } : {},
  };
});
