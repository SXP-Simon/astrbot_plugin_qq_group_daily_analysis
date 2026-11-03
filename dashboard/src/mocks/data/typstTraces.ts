import type { TraceRecord, TraceSpan } from "../../entities/trace/model/types";

const scenes = [
  { id: "cached", name: "本地素材命中", status: "succeeded", recovered: false },
  { id: "live", name: "CDN 下载中", status: "running", recovered: false },
  { id: "network", name: "资源超时仍完成", status: "warning", recovered: false },
  { id: "recovered", name: "基础排版恢复", status: "warning", recovered: true },
  { id: "failed", name: "编译与恢复均失败", status: "failed", recovered: true },
  { id: "cancelled", name: "编译阶段取消", status: "aborted", recovered: false },
] as const;

export const mockTypstTraces: TraceRecord[] = scenes.map((scene, index) => {
  const traceId = `trace-typst-${scene.id}`;
  const started = Date.now() / 1000 - (scene.status === "running" ? 8 : 90 + index * 60);
  const spans: TraceSpan[] = [];
  let elapsed = 0;
  const addSpan = (stage: string, duration: number, status: string, payload: Record<string, unknown> = {}) => {
    spans.push({ span_id: `${traceId}-${stage}`, trace_id: traceId, stage_name: stage, status,
      started_at: started + elapsed / 1000, duration_ms: status === "running" ? null : duration,
      start_memory_mb: 88.2, end_memory_mb: status === "running" ? null : 88.6, delta_memory_mb: status === "running" ? null : 0.4,
      payload });
    elapsed += duration;
  };
  addSpan("CHECKPOINT_RESTORE", 80, "success", { resumed_from: "mock-report-checkpoint" });
  const parent: TraceSpan = {
    span_id: `${traceId}-render`, trace_id: traceId, stage_name: "RENDER_REPORT",
    status: scene.status === "running" ? "running" : scene.status === "failed" ? "failed" : scene.status === "aborted" ? "aborted" : "success",
    started_at: started + elapsed / 1000, duration_ms: null,
    payload: { template: "HatsuneMiku", format: "image", render_attempts: [
      { attempt: 1, strategy_name: "Typst 本地方案", priority: 5, service_type: "typst",
        font_mode: "local", type: "png", viewport: "Typst 固定 940px", render_timeout_ms: 30000,
        status: scene.status === "running" ? "running" : scene.status === "failed" ? "failed" : scene.status === "aborted" ? "cancelled" : "success",
        render_service: { config_lookup: "插件独立 Typst 编译器", configured_endpoint: "本地隔离进程" } },
    ] },
  };
  spans.push(parent);
  addSpan("TYPST_VALIDATE", 3, "success", { template: "HatsuneMiku", width: 940 });
  addSpan("TYPST_DATA", 120, "success", { topics: 3, portraits: 4, quotes: 2 });
  const resources: Record<string, unknown> = { local_resources: scene.id === "cached" ? 10 : 2,
    image_cache_hits: scene.id === "cached" ? 9 : 0, downloaded_resources: scene.id === "live" ? 4 : 0,
    missing_resources: scene.id === "network" ? 2 : 0, missing_images: scene.id === "network" ? 1 : 0,
    network_budget_exhausted: scene.id === "network" };
  if (scene.id === "network") resources.warning = "部分素材请求超时，保留正文并继续排版；可在配置中心下载主题素材或切换 CDN";
  addSpan("TYPST_RESOURCES", scene.id === "network" ? 19800 : scene.id === "live" ? 7797 : 60,
    scene.id === "live" ? "running" : "success", resources);
  if (scene.status !== "running") {
    const compileStatus = scene.status === "aborted" ? "aborted" : scene.recovered ? scene.status === "failed" ? "failed" : "warning" : "success";
    const compilePayload: Record<string, unknown> = { template: "HatsuneMiku", width: 940 };
    if (scene.recovered) {
      if (scene.status === "failed") compilePayload.error = "主题第 18 行：预期长度，得到字符串";
      else { compilePayload.failure_reason = "主题第 18 行：预期长度，得到字符串"; compilePayload.warning = "主题编译失败，基础排版已恢复完整报告"; }
    } else if (scene.status !== "aborted") Object.assign(compilePayload, { font_setup_ms: 85, layout_ms: 190, raster_ms: 670, worker_peak_rss_mb: 156.9 });
    addSpan("TYPST_COMPILE", scene.recovered ? 310 : 945, compileStatus, compilePayload);
    if (scene.recovered) addSpan("TYPST_RECOVERY", 530, scene.status === "failed" ? "failed" : "success",
      scene.status === "failed" ? { mode: "basic", reason: "主题类型错误", error: "基础恢复也超出本轮编译预算" }
        : { mode: "basic", reason: "主题类型错误", font_setup_ms: 82, layout_ms: 65, raster_ms: 380, worker_peak_rss_mb: 119.3 });
    if (scene.status !== "failed" && scene.status !== "aborted") {
      addSpan("TYPST_ENCODE", 9, "success", { format: "png", image_bytes: 382910 });
      addSpan("DISPATCH_REPORT", 280, "success", { target_group: `typst-demo-${index}`, platform: "aiocqhttp", formats: ["image"], success: true });
    }
    parent.duration_ms = elapsed - 80 - (scene.status === "failed" || scene.status === "aborted" ? 0 : 280);
  }
  return { trace_id: traceId, group_id: `typst-demo-${index}`, group_name: `Typst · ${scene.name}`,
    platform: "aiocqhttp", trigger_type: "web_ui", status: scene.status,
    started_at: started, completed_at: scene.status === "running" ? null : started + elapsed / 1000,
    duration_ms: scene.status === "running" ? null : elapsed, current_stage: spans[spans.length - 1].stage_name, spans,
    error_stage: scene.status === "failed" ? "TYPST_RECOVERY" : scene.status === "aborted" ? "TYPST_COMPILE" : null,
    error_message: scene.status === "failed" ? "所有配置的渲染方案均失败" : scene.status === "aborted" ? "用户主动中止任务" : null,
    performance_metrics: { trace_id: traceId, init_memory_mb: 88.2, peak_memory_mb: 89.4, final_memory_mb: 88.8, delta_memory_mb: 0.6 },
    extra: { ...(scene.status === "warning" ? { has_warnings: true } : {}) },
  };
});
