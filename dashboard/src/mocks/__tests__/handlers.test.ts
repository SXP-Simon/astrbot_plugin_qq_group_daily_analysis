import { renderingConfigSchema } from "../../entities/config/model/renderingConfig";
import { describe, it, expect } from "vitest";
import { mockHandlers } from "../handlers";
import { createMswHandlerDefinitions } from "../mswHandlers";
import { mockTraces } from "../data/traces";
import { groupItemSchema } from "../../entities/group/model/types";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import configSchema from "../../../../_conf_schema.json";
import { mockPluginConfig } from "../data/configs";
import { mockCheckpoints } from "../data/pluginData";
import { extractData } from "../../shared/api/bridge";
import { mockActiveTasks } from "../data/tasks";

it("字体上传 Mock 只有末块才发布文件，取消后拒绝迟到分块", () => {
  const name = "mock-chunk-font.ttf",
    download_id = "chunk-upload-test";
  expect(
    mockHandlers["POST plugin-data/files/upload/start"]({
      download_id,
      partition: "typst_fonts",
      name,
      operation: "create",
      total: 1024,
    }).status,
  ).toBe("ok");
  expect(
    mockHandlers["POST plugin-data/files/upload"]({ download_id, offset: 0, chunk_bytes: 512 })
      .data,
  ).toMatchObject({ received: 512, complete: false });
  expect(
    mockHandlers["GET plugin-data/files/content"]({ partition: "typst_fonts", name }).status,
  ).toBe("error");
  expect(
    mockHandlers["POST plugin-data/files/upload/cancel"]({ download_id }).data?.cancelled,
  ).toBe(true);
  expect(
    mockHandlers["POST plugin-data/files/upload"]({ download_id, offset: 512, chunk_bytes: 512 })
      .status,
  ).toBe("error");
});

it("手动触发的 Mock 任务进入活跃列表，中止后历史记录收敛为已中止", () => {
  const response = mockHandlers["POST tasks/trigger"]({
    group_id: "QQ_OPENID",
    group_name: "取消测试群",
    platform: "qq_official_main",
  });
  const traceId = response.data!.trace_id;
  try {
    expect(
      mockActiveTasks.some((task) => task.task_id === traceId && task.trigger_type === "web_ui"),
    ).toBe(true);
    expect(mockHandlers["POST tasks/cancel"]({ task_id: traceId }).status).toBe("ok");
    expect(mockActiveTasks.some((task) => task.task_id === traceId)).toBe(false);
    expect(mockTraces.find((trace) => trace.trace_id === traceId)).toMatchObject({
      status: "aborted",
      error_message: "由 WebUI 手动取消任务",
    });
    expect(mockHandlers["POST tasks/cancel"]({ task_id: traceId }).status).toBe("error");
    expect(mockHandlers["POST tasks/cancel"]({ task_id: "missing-task" }).status).toBe("error");
  } finally {
    const index = mockTraces.findIndex((trace) => trace.trace_id === traceId);
    if (index >= 0) mockTraces.splice(index, 1);
    const activeIndex = mockActiveTasks.findIndex((task) => task.task_id === traceId);
    if (activeIndex >= 0) mockActiveTasks.splice(activeIndex, 1);
  }
});

it("快照 Mock 按请求身份读取真实 data 结构，并拒绝缺失或不匹配的身份", () => {
  const item = mockCheckpoints.items[1];
  const params = {
    group_id: item.group_id,
    date_str: item.date_str,
    stage_name: item.stage_name,
    trace_id: item.trace_id,
  };
  expect(extractData(mockHandlers["GET data/checkpoint/detail"](params))).toMatchObject({
    ...params,
    checkpoint_id: item.checkpoint_id,
    data: { group_id: item.group_id, stage_name: item.stage_name },
  });
  expect(
    mockHandlers["GET data/checkpoint/detail"]({ ...params, trace_id: "missing" }).status,
  ).toBe("error");
  expect(mockHandlers["GET data/checkpoint/detail"]().status).toBe("error");
});

it("配置 Mock 持久保留修改、更新回执版本并拒绝过期快照", () => {
  const initial = mockHandlers["GET config"]().data;
  try {
    const saved = mockHandlers["POST config"]({
      config: { basic: { ...initial.config.basic, max_topics: 5 } },
      revision: initial.revision,
    });
    expect(saved.status).toBe("ok");
    expect(saved).not.toHaveProperty("data");
    const updated = mockHandlers["GET config"]().data;
    expect(saved).toHaveProperty("revision", updated.revision);
    expect(updated.revision).not.toBe(initial.revision);
    expect(updated.config.basic.max_topics).toBe(5);
    const stale = mockHandlers["POST config"]({
      config: { basic: { max_topics: 9 } },
      revision: initial.revision,
    });
    expect(stale.status).toBe("error");
    expect(mockHandlers["GET config"]().data.config.basic.max_topics).toBe(5);
    const next = mockHandlers["POST config"]({
      config: { basic: { max_topics: 7 } },
      revision: updated.revision,
    });
    expect(next.status).toBe("ok");
    expect(mockHandlers["GET config"]().data.config.basic.max_topics).toBe(7);
  } finally {
    mockPluginConfig.config = initial.config;
  }
});

describe("Mock 路由分发器与数据源 (Mock Handlers & Dispatcher)", () => {
  it("演示配置使用真实结构并提供Typst与默认HTML后备", () => {
    const { config, schema } = mockHandlers["GET config"]().data;
    expect(Object.keys(schema).sort()).toEqual(Object.keys(configSchema).sort());
    expect(Object.keys(config).sort()).toEqual(Object.keys(configSchema).sort());
    const plans = renderingConfigSchema.parse(config.t2i_rendering).t2i_rendering_strategies || [];
    expect(plans[0].__template_key).toBe("typst");
    expect(plans.slice(1)).toEqual(
      renderingConfigSchema.parse({
        t2i_rendering_strategies: configSchema.t2i_rendering.items.t2i_rendering_strategies.default,
      }).t2i_rendering_strategies,
    );
    expect(config.prompts).toHaveProperty("topic_analysis_prompts");
  });

  it("日志分类使用后端的 key 和 label，且可以筛选", () => {
    const logs = mockHandlers["GET logs"]();
    expect(logs.data.items[0].timestamp).toBeLessThan(100000000000);
    expect(logs.data.items[0].time_str).toMatch(/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}$/);
    const tag = logs.data.available_tags.find((item) => item.key === "LLM");
    expect(tag).toEqual({ key: "LLM", label: "大模型调用" });
    const filtered = mockHandlers["GET logs"]({ tag: "LLM" });
    expect(filtered.data.items.length).toBeGreaterThan(0);
    expect(filtered.data.items.every((item) => item.tag === "LLM")).toBe(true);
  });

  it("平台数据和真实接口一致，包含平台实例和显示名称", () => {
    const platforms = mockHandlers["GET platforms"]().data;
    expect(platforms.length).toBeGreaterThan(0);
    expect(platforms.every((item) => item.id && item.type && item.display_name && item.label)).toBe(
      true,
    );
    expect(platforms.some((item) => "name" in item)).toBe(false);
  });
  it("群列表与真实后端契约一致，包含可显示的群名和平台实例", () => {
    const res = mockHandlers["GET groups"]();
    expect(res.data.length).toBeGreaterThan(0);
    for (const group of res.data) {
      expect(groupItemSchema.safeParse(group).success).toBe(true);
      expect(group.group_name).not.toBe("");
      expect(group.platform).not.toBe("");
    }
  });
  it("应当返回包含核心 KPI 字段的指标大盘概览数据", () => {
    const res = mockHandlers["GET metrics/summary"]();
    expect(res.status).toBe("ok");
    expect(res.data).toBeDefined();
    expect(res.data.total_traces).toBeGreaterThan(0);
    expect(res.data.success_rate).toBeGreaterThan(0);
  });

  it("应当支持按任务状态对链路列表进行过滤筛选", () => {
    const allRes = mockHandlers["GET traces"]();
    expect(allRes.data.items.length).toBeGreaterThan(0);

    const filteredRes = mockHandlers["GET traces"]({ status: "failed" });
    expect(filteredRes.data.items.every((t) => t.status === "failed")).toBe(true);
  });

  it("任务详情使用真实阶段、秒级时间戳和消息留存比例", () => {
    for (const trace of mockTraces) {
      expect(trace.started_at).toBeLessThan(100000000000);
      for (const span of trace.spans || []) expect(span.started_at).toBeLessThan(100000000000);
      if (trace.context_metrics && trace.context_metrics.raw_message_count > 0) {
        expect(trace.context_metrics.compression_ratio).toBeCloseTo(
          trace.context_metrics.cleaned_message_count / trace.context_metrics.raw_message_count,
          4,
        );
      }
    }
    const detail = mockHandlers["GET traces/:traceId"](undefined, {
      traceId: "trace-20260926-001",
    }).data;
    expect(detail?.spans?.map((span) => span.stage_name)).toEqual([
      "FETCH_MESSAGES",
      "CLEAN_MESSAGES",
      "STATS_ANALYSIS",
      "LLM_ANALYSIS",
      "SAVE_SUMMARY",
      "RENDER_REPORT",
      "DISPATCH_REPORT",
    ]);
    expect(
      detail?.spans?.find((span) => span.stage_name === "RENDER_REPORT")?.payload?.render_attempts,
    ).toHaveLength(2);
    expect(
      detail?.spans?.every(
        (span) => span.status === "success" && typeof span.end_memory_mb === "number",
      ),
    ).toBe(true);
  });

  it("运行中任务的时间和详情对应同一会话", () => {
    const tasks = mockHandlers["GET tasks/active"]().data;
    for (const task of tasks) {
      expect(task.started_at).toBeLessThan(100000000000);
      const detail = mockHandlers["GET traces/:traceId"](undefined, { traceId: task.task_id }).data;
      expect(detail).toMatchObject({
        trace_id: task.task_id,
        group_id: task.group_id,
        status: "running",
        current_stage: task.current_stage,
      });
    }
    expect(mockHandlers["GET traces/:traceId"](undefined, { traceId: "missing" }).data).toBeNull();
  });

  it("应当支持带动态参数的链路详情查询", () => {
    const res = mockHandlers["GET traces/:traceId"](undefined, { traceId: "trace-20260926-001" });
    expect(res.status).toBe("ok");
    expect(res.data?.trace_id).toBe("trace-20260926-001");
    expect(Array.isArray(res.data?.spans)).toBe(true);
  });

  it("提供 3 套覆盖完整业务场景的高保真 Golden Mocks (正常分析/超时中断/多模态漫画)", () => {
    expect(mockTraces.length).toBeGreaterThanOrEqual(3);
    const successTrace = mockTraces.find(
      (t) => t.status === "succeeded" && !t.extra?.comic_enabled,
    );
    const failedTrace = mockTraces.find((t) => t.trace_id === "trace-20260926-004-timeout");
    const comicTrace = mockTraces.find((t) => t.extra?.comic_enabled);

    expect(successTrace).toBeDefined();
    expect(failedTrace).toBeDefined();
    expect(comicTrace).toBeDefined();
    expect(failedTrace?.error_message).toContain("Connection timeout");
    expect(comicTrace?.spans?.some((s) => s.stage_name === "comic_generation")).toBe(true);
  });

  it("手动触发未指定群聊时拒绝创建 Mock 任务", () => {
    const res = mockHandlers["POST tasks/trigger"]();
    expect(res.status).toBe("error");
  });

  it("应当返回可用的海报视觉主题模板列表", () => {
    const res = mockHandlers["GET reports/templates"]();
    expect(res.status).toBe("ok");
    expect(Array.isArray(res.data)).toBe(true);
    expect(res.data.some((t) => t.id === "scrapbook")).toBe(true);
    for (const template of res.data.filter((item) => !item.is_custom)) {
      expect(existsSync(resolve(process.cwd(), "../assets", `${template.id}-demo.webp`))).toBe(
        true,
      );
    }
  });

  it("应当正确生成符合 MSW 标准规范的 Handler 定义列表", () => {
    const defs = createMswHandlerDefinitions("/api/plugins/astrbot_plugin_qq_group_daily_analysis");
    expect(defs.length).toBeGreaterThan(15);
    const getTracesDef = defs.find((d) => d.method === "GET" && d.path === "traces");
    expect(getTracesDef).toBeDefined();
    expect(getTracesDef?.urlPattern).toBe(
      "/api/plugins/astrbot_plugin_qq_group_daily_analysis/traces",
    );

    const resolved = getTracesDef?.resolver({ query: { status: "succeeded" } });
    expect(resolved?.status).toBe("ok");
  });
});

it("Typst演示覆盖本地缓存、下载、超时、恢复、失败和取消，活跃详情保持一致", () => {
  const native = mockTraces.filter((trace) => trace.trace_id.startsWith("trace-typst-"));
  expect(native).toHaveLength(12);
  const timeout = native.find((trace) => trace.trace_id === "trace-typst-compile-timeout");
  expect(timeout?.status).toBe("warning");
  expect(
    timeout?.spans?.find((span) => span.stage_name === "TYPST_COMPILE")?.payload,
  ).toMatchObject({
    requested_raster_ppi: 180,
    worker_metrics_partial: true,
    worker_phase: "raster",
    failure_reason: expect.stringContaining("20.00 秒预算（请求 180 PPI）"),
  });
  expect(
    timeout?.spans?.find((span) => span.stage_name === "TYPST_RECOVERY")?.payload,
  ).toMatchObject({ original_raster_ppi: 180, raster_ppi: 144 });
  const titleFallback = native.find((trace) => trace.trace_id === "trace-typst-title-font");
  expect(titleFallback?.status).toBe("warning");
  expect(
    titleFallback?.spans?.find((span) => span.stage_name === "TYPST_RESOURCES")?.payload,
  ).toMatchObject({
    title_font: "Noto Sans SC",
    warning: expect.stringContaining("初音标题字体尚未下载"),
  });
  for (const trace of native) {
    for (const span of trace.spans || []) {
      const measured = ["font_setup_ms", "layout_ms", "raster_ms"].reduce(
        (sum, key) =>
          sum + (typeof span.payload?.[key] === "number" ? Number(span.payload[key]) : 0),
        0,
      );
      if (span.duration_ms != null) expect(measured).toBeLessThanOrEqual(span.duration_ms);
    }
    const byId = new Map(trace.spans?.map((span) => [span.span_id, span]));
    expect(byId.size).toBe(trace.spans?.length);
    for (const span of trace.spans || []) {
      if (!span.stage_name.startsWith("TYPST_")) continue;
      const parent = byId.get(String(span.payload?.parent_span_id));
      expect(parent?.stage_name).toBe("IMAGE_RENDER_ATTEMPT");
      expect(byId.get(String(parent?.payload?.parent_span_id))?.stage_name).toBe("RENDER_REPORT");
    }
  }
  for (const id of ["fonts", "theme", "fallback", "html-native"]) {
    const trace = native.find((item) => item.trace_id === `trace-typst-${id}`);
    expect(trace?.spans?.filter((span) => span.stage_name === "IMAGE_RENDER_ATTEMPT")).toHaveLength(
      2,
    );
    expect(trace?.spans?.at(-1)?.stage_name).toBe("DISPATCH_REPORT");
  }
  const recovered = native.find((trace) => trace.trace_id === "trace-typst-recovered");
  expect(recovered?.status).toBe("warning");
  expect(recovered?.spans?.find((span) => span.stage_name === "TYPST_COMPILE")?.status).toBe(
    "warning",
  );
  expect(
    recovered?.spans?.find((span) => span.stage_name === "TYPST_RECOVERY")?.payload
      ?.worker_peak_rss_mb,
  ).toBeGreaterThan(0);
  expect(
    recovered?.spans?.find((span) => span.stage_name === "TYPST_RECOVERY")?.payload,
  ).toMatchObject({
    worker_rss_source: "linux_proc_status",
    worker_start_rss_mb: 11.8,
    worker_peak_delta_mb: 107.5,
  });
  expect(recovered?.spans?.at(-1)?.stage_name).toBe("DISPATCH_REPORT");
  for (const trace of native.filter(
    (trace) => trace.status === "failed" || trace.status === "aborted",
  )) {
    expect(trace.spans?.some((span) => span.stage_name === "DISPATCH_REPORT")).toBe(false);
  }
  const live = mockHandlers["GET tasks/active"]().data.find(
    (task) => task.task_id === "trace-typst-live",
  );
  expect(live?.current_stage).toBe("TYPST_RESOURCES");
});
it("模板安装的两种入口均同步模板目录与能力列表，卸载后完整移除", () => {
  for (const [endpoint, name] of [
    ["POST templates/install_from_url", "mock_installed_url"],
    ["POST templates/install_from_file", "mock_installed_zip"],
  ] as const) {
    const installed = mockHandlers[endpoint]({ name });
    expect(installed.status).toBe("ok");
    expect(installed.data?.name).toBe(name);
    expect(
      mockHandlers["GET reports/templates"]().data.find((item) => item.id === name),
    ).toMatchObject({ is_custom: true, has_typst: true, can_uninstall: true });
    const files = mockHandlers["GET plugin-data/files"]({
      partition: "custom_templates",
      directory: name,
    }).data;
    expect(files.total).toBe(2);
    expect(files.groups.find((item) => item.directory === name)?.count).toBe(2);
    expect(mockHandlers[endpoint]({ name }).status).toBe("error");
    expect(mockHandlers["POST templates/uninstall"]({ name }).data).toEqual({
      name,
      removed: true,
    });
    expect(
      mockHandlers["GET plugin-data/files"]({ partition: "custom_templates", directory: name }).data
        .total,
    ).toBe(0);
    expect(mockHandlers["GET reports/templates"]().data.some((item) => item.id === name)).toBe(
      false,
    );
  }
});
it("手动创建的模板可被识别，缺少入口的草稿也能整目录移除", () => {
  for (const [name, entry] of [
    ["mock_manual_remove", "report.typ"],
    ["mock_draft_remove", "template.json"],
  ] as const) {
    expect(
      mockHandlers["POST plugin-data/files/mutate"]({
        partition: "custom_templates",
        operation: "create",
        name: `${name}/${entry}`,
        content_base64: btoa("test"),
      }).status,
    ).toBe("ok");
    if (entry === "report.typ")
      expect(
        mockHandlers["GET reports/templates"]().data.find((item) => item.id === name),
      ).toMatchObject({ has_typst: true, can_uninstall: true });
    expect(mockHandlers["POST templates/uninstall"]({ name }).data).toEqual({
      name,
      removed: true,
    });
    expect(
      mockHandlers["GET plugin-data/files"]({ partition: "custom_templates", directory: name }).data
        .total,
    ).toBe(0);
  }
});
