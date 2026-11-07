import { managedRecordMockHandlers } from "./data/managedRecords";
import { managedMockFiles, putManagedMockFile, managedFileMockHandlers } from "./data/managedFiles";
import { mockTemplateResources, mockTypstFonts } from "./data/templateResources";
import { supportsTemplate } from "../entities/report/model/templates";
import { renderingRuntimeSchema } from "../entities/config/model/renderingConfig";
import { mockFontDownloadProgress, mockFontDownloads } from "./data/fontDownloads";
import { mockMetricsSummary, createMockAnalyticsTrends } from "./data/metrics";
import { mockActiveTasks, mockConnectedPlatforms } from "./data/tasks";
import { mockTraces } from "./data/traces";
import { mockReportHistory, mockReportTemplates } from "./data/reports";
import { mockReportHtml, mockReportImage, mockReportImageBytes } from "./data/reportContent";
import { configMockHandlers, mockPluginConfig, mockProviders, mockPersonas } from "./data/configs";
import { mockPluginLogs } from "./data/logs";
import { mockConfigBackups } from "./data/configBackups";
import { mockGroups } from "./data/groups";
import { mockSSEService } from "./sseMock";
import { TAG_STYLE_MAP } from "../entities/log/model/types";
import type { AvailableTag } from "../entities/log/model/types";
import {
  mockPluginDataOverview,
  mockCheckpoints,
  mockIncrementalSessions,
  incrementalMockSession,
} from "./data/pluginData";

/**
 * 标准化的 Mock Handlers 路由匹配表
 * 结构遵循 RESTful API 规范，完全兼容未来无缝迁移至 MSW (Mock Service Worker)
 */
export interface MockHandlerResponse<T = unknown> {
  status?: string | number;
  data?: T;
  message?: string;
  [key: string]: unknown;
}

const cancelledDownloads = new Set<string>();
const mockUploads = new Map<
  string,
  {
    name: string;
    partition: string;
    total: number;
    received: number;
    operation: string;
    revision: string;
  }
>();
const cancelledUploads = new Set<string>();

export const mockHandlers = {
  "POST plugin-data/files/upload/start": (body?: Record<string, unknown>) => {
    const id = String(body?.download_id || ""),
      name = String(body?.name || ""),
      total = Number(body?.total);
    if (cancelledUploads.has(id)) return { status: "error", message: "上传已取消" };
    if (
      !id ||
      !name ||
      mockUploads.has(id) ||
      !Number.isInteger(total) ||
      total <= 0 ||
      total > 32 * 1024 * 1024
    )
      return { status: "error", message: "上传参数无效" };
    mockUploads.set(id, {
      name,
      partition: String(body?.partition),
      total,
      received: 0,
      operation: String(body?.operation),
      revision: String(body?.revision || ""),
    });
    return { status: "ok", data: { upload_id: id } };
  },
  "POST plugin-data/files/upload": (body?: Record<string, unknown>) => {
    const id = String(body?.download_id || "");
    const offset = Number(body?.offset),
      bytes = Number(body?.chunk_bytes);
    if (cancelledUploads.has(id)) return { status: "error", message: "上传已取消" };
    const current = mockUploads.get(id);
    if (
      !current ||
      bytes <= 0 ||
      bytes > 1024 * 1024 ||
      offset !== current.received ||
      offset + bytes > current.total
    )
      return { status: "error", message: "上传分块不匹配" };
    const { name, total } = current;
    current.received += bytes;
    mockUploads.set(id, current);
    const complete = current.received === total;
    if (complete) {
      const saved = managedMockFiles.get(current.partition)?.get(name);
      if (
        current.operation === "create" ? !!saved : !saved || current.revision !== saved.revision
      ) {
        mockUploads.delete(id);
        return { status: "error", message: "文件已变更或目标已存在，请刷新" };
      }
      putManagedMockFile(current.partition, name, null, "AAEAAAAA");
      mockUploads.delete(id);
      if (current.partition === "typst_fonts") {
        mockTypstFonts.files = [...new Set([...mockTypstFonts.files, name])];
        mockTypstFonts.missing = mockTypstFonts.missing.filter((file) => file !== name);
        mockTypstFonts.ready = !mockTypstFonts.missing.length;
        mockTypstFonts.groups?.forEach((group) => {
          group.missing = group.required.filter((file) => !mockTypstFonts.files.includes(file));
          group.ready = !group.missing.length;
        });
      }
    }
    return { status: "ok", data: { received: current.received, total, complete } };
  },
  "POST plugin-data/files/upload/cancel": (body?: Record<string, unknown>) => {
    const id = String(body?.download_id || "");
    if (!id) return { status: "error", message: "上传标识无效" };
    if (cancelledUploads.size >= 1024) cancelledUploads.clear();
    cancelledUploads.add(id);
    mockUploads.delete(id);
    return { status: "ok", data: { download_id: id, cancelled: true } };
  },
  "POST config/downloads/cancel": (body?: Record<string, unknown>) => {
    if (typeof body?.download_id !== "string") return { status: "error", message: "下载标识无效" };
    if (cancelledDownloads.size >= 1024) cancelledDownloads.clear();
    cancelledDownloads.add(body.download_id);
    mockFontDownloads.delete(body.download_id);
    return { status: "ok", data: { download_id: body.download_id, cancelled: true } };
  },
  "POST config/downloads/progress": (body?: Record<string, unknown>) => ({
    status: "ok",
    data: mockFontDownloadProgress(String(body?.download_id)),
  }),
  ...configMockHandlers,
  ...managedFileMockHandlers,
  ...managedRecordMockHandlers,
  "POST config/test-t2i": () => ({
    status: "error",
    message: "演示模式不进行真实渲染，请连接 AstrBot 插件后再试。",
  }),
  "POST config/test-template-cdn": () => ({
    status: "error",
    message: "演示模式不进行真实网络检测，请连接 AstrBot 插件后再试。",
  }),
  "GET config/template-resources": () => {
    const files = managedMockFiles.get("template_resources");
    mockTemplateResources.groups.forEach((group) =>
      group.files.forEach((file) => {
        file.available = files?.has(file.name) || false;
      }),
    );
    return { status: "ok", data: mockTemplateResources };
  },
  "POST config/template-resources/download": (body?: Record<string, unknown>) => {
    if (typeof body?.download_id === "string" && cancelledDownloads.has(body.download_id)) {
      return { status: "error", message: "下载已取消，已完成的文件会保留" };
    }
    const file = mockTemplateResources.groups
      .flatMap((group) => group.files)
      .find((item) => item.name === body?.name);
    if (!file) return { status: "error", message: "演示素材不在清单中" };
    if (
      file.name === "scrapbook/assistant.jpg" &&
      String(body?.cdn_base_url).includes("jsdmirror")
    ) {
      return { status: "error", message: "演示：当前 CDN 的角色图片请求超时，可更换 CDN 后重试" };
    }
    file.available = true;
    if (file.name.endsWith(".svg"))
      putManagedMockFile(
        "template_resources",
        file.name,
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100"><circle cx="50" cy="50" r="45" fill="#39c5bb"/></svg>',
      );
    else
      putManagedMockFile(
        "template_resources",
        file.name,
        null,
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a27sAAAAASUVORK5CYII=",
      );
    return { status: "ok", data: { ...file } };
  },
  "GET config/typst-fonts": () => {
    mockTypstFonts.files = [...(managedMockFiles.get("typst_fonts")?.keys() || [])];
    mockTypstFonts.groups?.forEach((group) => {
      group.missing = group.required.filter((file) => !mockTypstFonts.files.includes(file));
      group.ready = !group.missing.length;
    });
    mockTypstFonts.missing = [
      ...new Set(mockTypstFonts.groups?.flatMap((group) => group.missing) || []),
    ];
    mockTypstFonts.ready = !mockTypstFonts.missing.length;
    return { status: "ok", data: mockTypstFonts };
  },
  "POST config/typst-fonts/download": (body?: Record<string, unknown>) => {
    if (body?.source != null && !["cdn", "github"].includes(String(body.source)))
      return { status: "error", message: "未知字体下载来源" };
    if (typeof body?.download_id === "string" && cancelledDownloads.has(body.download_id)) {
      return { status: "error", message: "下载已取消，已完成的文件会保留" };
    }
    const theme = body?.theme;
    const selected = mockTypstFonts.groups?.find((group) => group.theme === theme);
    if (theme != null && !selected) return { status: "error", message: "未知 Typst 模板" };
    const allowed = selected?.required || [
      ...new Set(mockTypstFonts.groups?.flatMap((group) => group.required) || []),
    ];
    if (body?.name != null && (typeof body.name !== "string" || !allowed.includes(body.name)))
      return { status: "error", message: "字体不属于所选预设" };
    if (
      body?.source !== "github" &&
      body?.name === "Cinzel.ttf" &&
      String(body.cdn_base_url).includes("jsdmirror")
    )
      return {
        status: "error",
        message: "演示：Cinzel.ttf 来源返回 HTTP 403，可切换 GitHub Raw 后重试，或上传同名字体",
      };
    const names = (selected?.missing || mockTypstFonts.missing).filter(
      (name) => body?.name == null || name === body.name,
    );
    names.forEach((name) => putManagedMockFile("typst_fonts", name, null, "AAEAAAAA"));
    mockTypstFonts.files = [...new Set([...mockTypstFonts.files, ...names])];
    mockTypstFonts.missing = mockTypstFonts.missing.filter((file) => !names.includes(file));
    mockTypstFonts.ready = !mockTypstFonts.missing.length;
    mockTypstFonts.groups?.forEach((group) => {
      group.missing = group.required.filter((file) => !mockTypstFonts.files.includes(file));
      group.ready = !group.missing.length;
    });
    return { status: "ok", data: mockTypstFonts };
  },
  // 1. 大盘指标与趋势
  "GET metrics/summary": () => ({ status: "ok", data: mockMetricsSummary }),
  "GET metrics/trends": (params?: Record<string, unknown>) => ({
    status: "ok",
    data: createMockAnalyticsTrends(
      params?.granularity === "hour" ? "hour" : "day",
      Number(params?.range_count ?? 14),
    ),
  }),

  // 2. 活跃任务与控制
  "GET tasks/active": () => ({ status: "ok", data: mockActiveTasks }),
  "GET platforms": () => ({ status: "ok", data: mockConnectedPlatforms }),
  "POST tasks/trigger": (body?: Record<string, unknown>) => {
    if (typeof body?.group_id !== "string" || !body.group_id.trim())
      return { status: "error", message: "请选择要分析的群聊" };
    if (typeof body.platform !== "string" || !body.platform.trim())
      return { status: "error", message: "请选择准确的平台实例" };
    if (
      mockActiveTasks.some(
        (task) => task.group_id === body.group_id && task.platform === body.platform,
      )
    )
      return { status: "error", message: "此会话的分析任务正在执行中，请稍后再试" };
    const now = Date.now() / 1000;
    const task = {
      task_id: `trace-manual-${crypto.randomUUID()}`,
      group_id: body.group_id,
      group_name: typeof body.group_name === "string" ? body.group_name : body.group_id,
      platform: body.platform,
      trigger_type: "web_ui",
      current_stage: "FETCH_MESSAGES",
      started_at: now,
      duration_s: 0,
      last_heartbeat: now,
    };
    mockActiveTasks.unshift(task);
    mockTraces.unshift({
      ...task,
      trace_id: task.task_id,
      status: "running",
      duration_ms: null,
      spans: [],
    });
    mockSSEService.emitManualEvent({ event: "task_started", data: task });
    return { status: "ok", data: { trace_id: task.task_id, message: "任务已成功提交排队" } };
  },
  "POST tasks/cancel": (body?: Record<string, unknown>) => {
    const index = mockActiveTasks.findIndex((task) => task.task_id === body?.task_id);
    if (index < 0) return { status: "error", message: "任务不存在或已经结束，请刷新后确认" };
    const [task] = mockActiveTasks.splice(index, 1);
    const trace = mockTraces.find((item) => item.trace_id === task.task_id);
    if (trace) {
      const completedAt = Date.now() / 1000;
      trace.status = "aborted";
      trace.completed_at = completedAt;
      trace.duration_ms = Math.max(0, (completedAt - trace.started_at) * 1000);
      trace.error_message = "由 WebUI 手动取消任务";
      trace.spans
        ?.filter((span) => span.status === "running")
        .forEach((span) => {
          span.status = "aborted";
          span.duration_ms = Math.max(0, (completedAt - span.started_at) * 1000);
        });
    }
    mockSSEService.emitManualEvent({ event: "task_canceled", data: { task_id: task.task_id } });
    return { status: "ok", data: { success: true } };
  },
  "POST tasks/:traceId/resume": (
    _body?: Record<string, unknown>,
    params?: Record<string, string>,
  ): MockHandlerResponse<{ trace_id: string; message: string }> => {
    const source = mockTraces.find((trace) => trace.trace_id === params?.traceId);
    if (!source) return { status: "error", message: "原任务不存在" };
    if (source.status === "running")
      return { status: "error", message: "任务仍在运行，不能重复续跑" };
    if (!source.platform)
      return { status: "error", message: "原任务未记录平台实例，请选择会话重新分析" };
    const response = mockHandlers["POST tasks/trigger"]({
      group_id: source.group_id,
      group_name: source.group_name,
      platform: source.platform,
    });
    if (response.data) {
      const task = mockActiveTasks.find((item) => item.task_id === response.data.trace_id);
      const trace = mockTraces.find((item) => item.trace_id === response.data.trace_id);
      if (task) task.trigger_type = "resume";
      if (trace) trace.trigger_type = "resume";
    }
    return response;
  },

  // 3. 链路追踪
  "GET traces": (params?: Record<string, unknown>) => {
    let items = [...mockTraces];
    if (params?.status && typeof params.status === "string" && params.status !== "ALL") {
      const states =
        params.status === "succeeded"
          ? ["succeeded", "completed"]
          : params.status === "aborted"
            ? ["aborted", "cancelled"]
            : [params.status];
      items = items.filter((t) => states.includes(t.status));
    }
    if (params?.group_id && typeof params.group_id === "string") {
      items = items.filter((t) => t.group_id === params.group_id);
    }
    if (typeof params?.platform === "string") {
      items = items.filter((t) => t.platform === params.platform);
    }
    if (typeof params?.trigger_type === "string" && params.trigger_type) {
      items = items.filter((t) => t.trigger_type === params.trigger_type);
    }
    if (typeof params?.search === "string" && params.search.trim()) {
      const search = params.search.trim().toLowerCase();
      items = items.filter((t) =>
        [t.trace_id, t.group_id, t.group_name].some((value) =>
          value.toLowerCase().includes(search),
        ),
      );
    }
    if (params?.start_time !== undefined && Number.isFinite(Number(params.start_time))) {
      items = items.filter((t) => t.started_at >= Number(params.start_time));
    }
    if (params?.end_time !== undefined && Number.isFinite(Number(params.end_time))) {
      items = items.filter((t) => t.started_at <= Number(params.end_time));
    }
    const field =
      params?.sort_by === "duration_ms" ||
      params?.sort_by === "total_tokens" ||
      params?.sort_by === "compression_ratio"
        ? params.sort_by
        : "started_at";
    const direction = params?.sort_order === "asc" ? 1 : -1;
    // 与 SQLite 一致：升序时缺失值在前，降序时在后，不把缺失值当作零。
    items.sort((left, right) => {
      const a = left[field],
        b = right[field];
      const tie =
        (left.trace_id < right.trace_id ? -1 : left.trace_id > right.trace_id ? 1 : 0) * direction;
      if (a == null && b == null) return tie;
      if (a == null) return -direction;
      if (b == null) return direction;
      return (a - b) * direction || tie;
    });
    if (typeof params?.before_time === "number" && typeof params.before_id === "string") {
      const time = params.before_time,
        id = params.before_id;
      items = items.filter(
        (item) => item.started_at < time || (item.started_at === time && item.trace_id < id),
      );
    }
    const total = items.length;
    const offset = Number.isFinite(Number(params?.offset))
      ? Math.max(0, Math.floor(Number(params?.offset)))
      : 0;
    const limit = Number.isFinite(Number(params?.limit))
      ? Math.max(1, Math.floor(Number(params?.limit)))
      : 20;
    return {
      status: "ok",
      data: { items: items.slice(offset, offset + limit), total, has_more: offset + limit < total },
    };
  },
  "GET traces/:traceId": (
    params?: Record<string, unknown>,
    pathParams?: Record<string, string>,
  ) => {
    const traceId = pathParams?.traceId || (params?.traceId as string);
    const item = mockTraces.find((t) => t.trace_id === traceId);
    if (item) return { status: "ok", data: item };
    const task = mockActiveTasks.find((t) => t.task_id === traceId);
    if (task)
      return {
        status: "ok",
        data: {
          trace_id: task.task_id,
          group_id: task.group_id,
          group_name: task.group_name,
          platform: task.platform,
          trigger_type: task.trigger_type,
          status: "running",
          current_stage: task.current_stage,
          started_at: task.started_at,
          duration_ms: task.duration_s * 1000,
          spans: [],
        },
      };
    return { status: "error", data: null, message: "未找到任务记录" };
  },
  "GET traces/:traceId/logs": (
    params?: Record<string, unknown>,
    pathParams?: Record<string, string>,
  ) => {
    const traceId = pathParams?.traceId || (params?.traceId as string);
    const logs = mockPluginLogs.filter((l) => l.trace_id === traceId);
    return { status: "ok", data: logs };
  },
  "GET groups": (params?: Record<string, unknown>) => ({
    status: "ok",
    data: params?.by_session
      ? [
          ...new Map(
            mockTraces.map((trace) => [
              JSON.stringify([trace.platform || "", trace.group_id]),
              {
                group_id: trace.group_id,
                group_name: trace.group_name || trace.group_id,
                platform: trace.platform || "",
              },
            ]),
          ).values(),
        ]
      : mockGroups,
  }),
  "GET providers": () => ({ status: "ok", data: mockProviders }),
  "GET personas": () => ({ status: "ok", data: mockPersonas }),

  // 4. 历史报告与海报模板
  "GET reports/history": (params?: Record<string, unknown>) => {
    let items = [...mockReportHistory];
    const group = typeof params?.group_id === "string" ? params.group_id.trim() : "";
    const search = typeof params?.search === "string" ? params.search.trim().toLowerCase() : "";
    if (group) items = items.filter((item) => item.group_id === group);
    if (typeof params?.platform === "string")
      items = items.filter((item) => (item.platform || "") === params.platform);
    if (search)
      items = items.filter((item) =>
        [item.filename, item.group_id, item.trace_id].some((value) =>
          value?.toLowerCase().includes(search),
        ),
      );
    if (params?.report_type && typeof params.report_type === "string") {
      items = items.filter((r) => r.report_type === params.report_type);
    }
    if (typeof params?.start_time === "number")
      items = items.filter(
        (item) => (item.modified_at ?? item.created_at ?? 0) >= Number(params.start_time),
      );
    if (typeof params?.end_time === "number")
      items = items.filter(
        (item) => (item.modified_at ?? item.created_at ?? 0) <= Number(params.end_time),
      );
    const direction = params?.sort_order === "asc" ? 1 : -1;
    items.sort(
      (a, b) =>
        ((a.modified_at ?? a.created_at ?? 0) - (b.modified_at ?? b.created_at ?? 0) ||
          (a.filename < b.filename ? -1 : a.filename > b.filename ? 1 : 0)) * direction,
    );
    const limit = Math.max(1, Math.min(100, Math.trunc(Number(params?.limit) || 20)));
    const offset = Math.max(0, Math.trunc(Number(params?.offset) || 0));
    return {
      status: "ok",
      data: { items: items.slice(offset, offset + limit), total: items.length },
    };
  },
  "GET reports/content": (params?: Record<string, unknown>) => {
    const item = mockReportHistory.find((report) => report.filename === params?.filename);
    if (!item) return { status: "error", message: "示例报告不存在，请刷新列表。" };
    const isHtml = item.is_html || /\.html?$/i.test(item.filename);
    return {
      status: "ok",
      data: {
        ...item,
        is_html: isHtml,
        html_content: isHtml ? mockReportHtml : undefined,
        data_url: isHtml ? undefined : mockReportImage,
      },
    };
  },
  "GET reports/templates": (params?: Record<string, unknown>) => {
    const files = managedMockFiles.get("custom_templates");
    const directories = new Set(
      [...(files?.keys() || [])]
        .filter((name) => name.includes("/"))
        .map((name) => name.split("/")[0]),
    );
    const templates = mockReportTemplates.filter(
      (item) => !item.is_custom || !directories.has(item.id),
    );
    for (const directory of directories) {
      const has_typst = files?.has(`${directory}/report.typ`) || false;
      const has_image = files?.has(`${directory}/image_template.html`) || false;
      const has_html = files?.has(`${directory}/html_template.html`) || false;
      if (!has_typst && !has_image && !has_html) continue;
      const known = mockReportTemplates.find((item) => item.id === directory && item.is_custom);
      templates.push({
        ...known,
        id: directory,
        label: known?.label || directory,
        is_custom: true,
        can_uninstall: true,
        has_typst,
        has_image,
        has_html,
      });
    }
    const output = params?.render_format;
    const runtime = renderingRuntimeSchema.safeParse(mockPluginConfig.config.t2i_rendering || {});
    const formats =
      output === "configured" ? mockPluginConfig.config.basic?.output_format : [output];
    const requirements =
      !output || output === "all"
        ? undefined
        : {
            engine: runtime.success ? runtime.data.template_engine : ("html" as const),
            formats: Array.isArray(formats)
              ? formats.filter((value): value is string => typeof value === "string")
              : ["image"],
          };
    return { status: "ok", data: templates.filter((item) => supportsTemplate(item, requirements)) };
  },
  "GET templates/preview": () => ({
    status: "ok",
    data: {
      data_url:
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='200'><rect width='100%' height='100%' fill='%2352c41a'/><text x='50%' y='50%' fill='white' font-size='18' text-anchor='middle'>Template Live Preview</text></svg>",
    },
  }),
  "POST templates/install_from_url": (body?: Record<string, unknown>) => {
    const name = String(body?.name || "custom_demo").trim();
    if (
      !name ||
      name.length > 50 ||
      name.startsWith(".") ||
      name.endsWith(".") ||
      /[\\/:*?"<>|]/.test(name) ||
      mockReportTemplates.some((item) => item.id === name) ||
      [...(managedMockFiles.get("custom_templates")?.keys() || [])].some((key) =>
        key.startsWith(name + "/"),
      )
    )
      return { status: "error", message: "模板名无效或目录已存在，请使用不同名称" };
    putManagedMockFile(
      "custom_templates",
      `${name}/report.typ`,
      "#set text(size: 12pt)\n= 演示模板",
    );
    putManagedMockFile(
      "custom_templates",
      `${name}/template.json`,
      JSON.stringify({ name: "在线安装演示模板" }),
    );
    mockReportTemplates.push({
      id: name,
      label: `在线安装演示模板 (${name})`,
      display_name: "在线安装演示模板",
      is_custom: true,
      has_typst: true,
      can_uninstall: true,
    });
    return {
      status: "ok",
      data: {
        name,
        label: "在线安装演示模板",
        has_typst: true,
        has_image: false,
        has_html: false,
        files: ["report.typ", "template.json"],
      },
    };
  },
  "POST templates/install_from_file": (body?: Record<string, unknown>) => {
    const name = String(body?.name || "custom_uploaded").trim();
    if (
      !name ||
      name.length > 50 ||
      name.startsWith(".") ||
      name.endsWith(".") ||
      /[\\/:*?"<>|]/.test(name) ||
      mockReportTemplates.some((item) => item.id === name) ||
      [...(managedMockFiles.get("custom_templates")?.keys() || [])].some((key) =>
        key.startsWith(name + "/"),
      )
    )
      return { status: "error", message: "模板名无效或目录已存在，请使用不同名称" };
    putManagedMockFile(
      "custom_templates",
      `${name}/report.typ`,
      "#set text(size: 12pt)\n= 演示模板",
    );
    putManagedMockFile(
      "custom_templates",
      `${name}/template.json`,
      JSON.stringify({ name: "上传安装演示模板" }),
    );
    mockReportTemplates.push({
      id: name,
      label: `上传安装演示模板 (${name})`,
      display_name: "上传安装演示模板",
      is_custom: true,
      has_typst: true,
      can_uninstall: true,
    });
    return {
      status: "ok",
      data: {
        name,
        label: "上传安装演示模板",
        has_typst: true,
        has_image: false,
        has_html: false,
        files: ["report.typ", "template.json"],
      },
    };
  },
  "POST templates/uninstall": (body?: Record<string, unknown>) => {
    const name = String(body?.name || "");
    const files = managedMockFiles.get("custom_templates");
    if (
      !name ||
      name.length > 50 ||
      name.startsWith(".") ||
      name.endsWith(".") ||
      /[\\/:*?"<>|]/.test(name) ||
      mockReportTemplates.some((item) => item.id === name && !item.is_custom) ||
      ![...(files?.keys() || [])].some((key) => key.startsWith(name + "/"))
    )
      return { status: "error", message: "模板目录不存在或不允许移除" };
    const index = mockReportTemplates.findIndex((item) => item.id === name && item.is_custom);
    if (index >= 0) mockReportTemplates.splice(index, 1);
    for (const key of files?.keys() || []) if (key.startsWith(name + "/")) files?.delete(key);
    return { status: "ok", data: { name, removed: true } };
  },
  "POST reports/rerender": (body?: Record<string, unknown>) => {
    const format = body?.render_format;
    if (format !== "html" && format !== "image")
      return { status: "error", message: "请选择图片或 HTML 格式。" };
    if (!body?.platform_id && !body?.trace_id)
      return { status: "error", message: "请选择平台实例或具体分析任务后重绘" };
    const source = mockReportHistory.find(
      (item) =>
        item.group_id === body?.group_id &&
        (!body?.trace_id || item.trace_id === body.trace_id) &&
        (!body?.platform_id || item.platform === body.platform_id),
    );
    if (!source) return { status: "error", message: "未找到这次分析的示例产物记录。" };
    if (
      body?.trace_id &&
      (!source.platform ||
        !mockTraces.some(
          (trace) => trace.trace_id === source.trace_id && trace.group_id === source.group_id,
        ))
    )
      return { status: "error", message: "无法确认原任务归属，已有报告仍可查看和下载" };
    const available = mockHandlers["GET reports/templates"]({ render_format: format }).data;
    if (!available.some((item) => item.id === body?.template_name))
      return { status: "error", message: "所选模板不支持当前输出格式。" };
    const isHtml = format === "html";
    const filename = `report_demo_${crypto.randomUUID()}.${isHtml ? "html" : "png"}`;
    const timestamp = Date.now() / 1000;
    const bytes = isHtml
      ? new TextEncoder().encode(mockReportHtml).byteLength
      : mockReportImageBytes;
    mockReportHistory.unshift({
      ...source,
      filename,
      created_at: timestamp,
      modified_at: timestamp,
      size_bytes: bytes,
      is_html: isHtml,
      is_comic: false,
      report_type: isHtml ? "html" : "image",
    });
    const trace = mockTraces.find((item) => item.trace_id === source.trace_id);
    if (trace)
      (trace.report_files ??= []).push({
        filename,
        format: isHtml ? "html" : "png",
        report_type: isHtml ? "html" : "image",
        size_bytes: bytes,
        created_at: timestamp,
      });
    return {
      status: "ok",
      data: {
        success: true,
        filename,
        report_path: `reports/${filename}`,
        is_html: isHtml,
      },
    };
  },

  // 5. 日志流
  "GET logs": (params?: Record<string, unknown>) => {
    let items = [...mockPluginLogs];
    if (typeof params?.trace_id === "string" && params.trace_id.trim()) {
      items = items.filter((item) => item.trace_id === String(params.trace_id).trim());
    }
    if (params?.level && typeof params.level === "string" && params.level !== "ALL") {
      items = items.filter((l) => l.level === params.level);
    }
    if (params?.tag && typeof params.tag === "string" && params.tag !== "ALL") {
      items = items.filter((l) => l.tag === params.tag);
    }
    if (params?.search && typeof params.search === "string") {
      const q = (params.search as string).toLowerCase();
      items = items.filter(
        (l) =>
          l.message.toLowerCase().includes(q) ||
          (l.raw && l.raw.toLowerCase().includes(q)) ||
          (l.logger_name && l.logger_name.toLowerCase().includes(q)) ||
          (l.location && l.location.toLowerCase().includes(q)) ||
          (l.function_name && l.function_name.toLowerCase().includes(q)) ||
          (l.trace_id && l.trace_id.toLowerCase().includes(q)),
      );
    }
    const tags: AvailableTag[] = Object.entries(TAG_STYLE_MAP).map(([key, value]) => ({
      key,
      label: value.label,
    }));
    return {
      status: "ok",
      data: {
        items,
        total: items.length,
        available_tags: tags,
      },
    };
  },

  // 6. 配置项
  "POST config/upload_file": () => ({
    status: "ok",
    data: { success: true, file_path: "files/custom_avatar.png" },
  }),
  "GET config/file/content": () => ({
    status: "ok",
    data: { content: "" },
  }),

  // 7. 数据存储管理
  "GET plugin-data/overview": () => ({ status: "ok", data: mockPluginDataOverview }),
  "GET plugin-data/config-backups": () => ({
    status: "ok",
    data: {
      items: mockConfigBackups
        .filter((item) => managedMockFiles.get("config_backups")?.has(item.backup.filename))
        .map((item) => ({
          ...item.backup,
          size_bytes: atob(
            managedMockFiles.get("config_backups")!.get(item.backup.filename)!.content_base64,
          ).length,
        })),
    },
  }),
  "GET plugin-data/config-backups/detail": (params?: Record<string, unknown>) => {
    const detail = mockConfigBackups.find((item) => item.backup.filename === params?.filename);
    return detail && managedMockFiles.get("config_backups")?.has(detail.backup.filename)
      ? { status: "ok", data: detail }
      : { status: "error", message: "备份不存在" };
  },
  "POST plugin-data/:section/clear": () => ({ status: "ok", data: { deleted: 10 } }),
  "GET data/incremental/groups": () => {
    const history = new Map(
      mockTraces.map((item) => [
        JSON.stringify([item.platform, item.group_id]),
        {
          group_id: item.group_id,
          group_name: item.group_name || "",
          platform_id: item.platform || "",
        },
      ]),
    );
    for (const key of mockIncrementalSessions.keys()) {
      if (!history.has(key)) {
        const [platform_id, group_id] = JSON.parse(key) as [string, string];
        history.set(key, { group_id, platform_id, group_name: "" });
      }
    }
    const group_details = [...history.values()];
    const groups = [...new Set(group_details.map((item) => item.group_id))].sort();
    return { status: "ok", data: { groups, group_details } };
  },
  "GET data/incremental/batches": (params?: Record<string, unknown>) => {
    const session = incrementalMockSession(
      String(params?.group_id || ""),
      String(params?.platform_id || ""),
    );
    const batches = session.batches
      .filter((item) => item.group_id === params?.group_id)
      .sort((a, b) => b.timestamp - a.timestamp || b.batch_id.localeCompare(a.batch_id));
    const pageSize = Math.min(100, Math.max(1, Number(params?.page_size) || 20));
    const page = Math.min(
      Math.max(1, Number(params?.page) || 1),
      Math.max(1, Math.ceil(batches.length / pageSize)),
    );
    return {
      status: "ok",
      data: {
        group_id: params?.group_id,
        platform_id: String(params?.platform_id || ""),
        cursor: session.cursor,
        total: batches.length,
        page,
        page_size: pageSize,
        batches: batches.slice((page - 1) * pageSize, page * pageSize),
      },
    };
  },
  "GET data/incremental/batch/detail": (params?: Record<string, unknown>) => {
    const response = managedRecordMockHandlers["GET plugin-data/records/detail"]({
      kind: "batch",
      group_id: params?.group_id,
      platform_id: params?.platform_id,
      batch_id: params?.batch_id,
    });
    return response.status === "ok" ? { status: "ok", data: response.data?.data } : response;
  },
  "POST data/incremental/batch": (params?: Record<string, unknown>) => {
    const locator = {
      kind: "batch",
      group_id: params?.group_id,
      platform_id: params?.platform_id,
      batch_id: params?.batch_id,
    };
    const current = managedRecordMockHandlers["GET plugin-data/records/detail"](locator);
    if (current.status !== "ok") return current;
    const result = managedRecordMockHandlers["POST plugin-data/records/mutate"]({
      locator,
      revision: current.data?.revision,
      operation: "delete",
    });
    return result.status === "ok" ? { status: "ok", data: { deleted: true } } : result;
  },
  "POST data/incremental/reset": (params?: Record<string, unknown>) => {
    const session = incrementalMockSession(
      String(params?.group_id || ""),
      String(params?.platform_id || ""),
    );
    const batches = session.batches.filter((batch) => batch.group_id === params?.group_id);
    for (const batch of batches) {
      const locator = {
        kind: "batch",
        group_id: batch.group_id,
        platform_id: params?.platform_id,
        batch_id: batch.batch_id,
      };
      const current = managedRecordMockHandlers["GET plugin-data/records/detail"](locator);
      const result = managedRecordMockHandlers["POST plugin-data/records/mutate"]({
        locator,
        revision: current.data?.revision,
        operation: "delete",
      });
      if (result.status !== "ok") return result;
    }
    {
      session.cursor = {
        group_id: session.group_id,
        timestamp: 0,
        last_analyzed_timestamp: 0,
        last_message_timestamp: 0,
        tracked_message_ids_count: 0,
      };
    }
    return { status: "ok", data: { deleted_batches: batches.length, message: "已重置增量状态" } };
  },
  "GET data/checkpoints/groups": () => ({
    status: "ok",
    data: {
      groups: [...new Set(mockCheckpoints.items.map((item) => item.group_id))],
      sessions: [
        ...new Map(
          mockCheckpoints.items.map((item) => {
            const trace = mockTraces.find(
              (trace) => trace.trace_id === item.trace_id && trace.group_id === item.group_id,
            );
            const session = {
              group_id: item.group_id,
              group_name: trace?.group_name || "",
              platform: trace?.platform || "",
            };
            return [JSON.stringify([session.platform, session.group_id]), session];
          }),
        ).values(),
      ],
    },
  }),
  "GET data/checkpoints": (params?: Record<string, unknown>) => {
    let items = mockCheckpoints.items.map((item) => {
      const trace = mockTraces.find(
        (trace) => trace.trace_id === item.trace_id && trace.group_id === item.group_id,
      );
      return { ...item, platform: trace?.platform || "", group_name: trace?.group_name || "" };
    });
    if (typeof params?.platform === "string")
      items = items.filter((item) => item.platform === params.platform);
    for (const key of ["group_id", "date_str", "stage_name", "trace_id"] as const) {
      if (params?.[key]) items = items.filter((item) => item[key] === params[key]);
    }
    items.sort(
      (a, b) =>
        (b.created_at ?? 0) - (a.created_at ?? 0) ||
        (b.checkpoint_id || "").localeCompare(a.checkpoint_id || ""),
    );
    const offset = Math.max(0, Number(params?.offset) || 0);
    const limit = Math.max(1, Number(params?.limit) || 50);
    return {
      status: "ok",
      data: { total: items.length, items: items.slice(offset, offset + limit) },
    };
  },
  "GET data/checkpoint/detail": (params?: Record<string, unknown>) => {
    if (!params?.group_id || !params.date_str || !params.stage_name)
      return { status: "error", message: "请提供群、日期和阶段以读取快照。" };
    const result = managedRecordMockHandlers["GET plugin-data/records/detail"]({
      kind: "checkpoint",
      ...params,
      trace_id: params.trace_id || "",
    });
    return result.status === "ok" ? { status: "ok", data: result.data?.data } : result;
  },
  "POST data/checkpoint": (params?: Record<string, unknown>) => {
    const locator = { kind: "checkpoint", ...params, trace_id: params?.trace_id || "" };
    const result = managedRecordMockHandlers["GET plugin-data/records/detail"](locator);
    if (result.status !== "ok" || !result.data)
      return { status: "error", message: "快照不存在或已过期，请刷新列表。" };
    const removed = managedRecordMockHandlers["POST plugin-data/records/mutate"]({
      locator,
      revision: result.data.revision,
      operation: "delete",
    });
    return removed.status === "ok" ? { status: "ok", data: { deleted: true } } : removed;
  },
};
