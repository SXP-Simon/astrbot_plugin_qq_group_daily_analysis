import { mockMetricsSummary, mockAnalyticsTrends } from "./data/metrics";
import { mockActiveTasks, mockConnectedPlatforms } from "./data/tasks";
import { mockTraces } from "./data/traces";
import { mockReportHistory, mockReportTemplates } from "./data/reports";
import { mockPluginConfig, mockProviders, mockPersonas } from "./data/configs";
import { mockPluginLogs } from "./data/logs";
import {
  mockPluginDataOverview,
  mockIncrementalBatches,
  mockCheckpoints,
} from "./data/pluginData";

/**
 * 标准化的 Mock Handlers 路由匹配表
 * 结构遵循 RESTful API 规范，完全兼容未来无缝迁移至 MSW (Mock Service Worker)
 */
export interface MockHandlerResponse<T = unknown> {
  status?: number;
  data?: T;
  message?: string;
  [key: string]: unknown;
}

export const mockHandlers = {
  // 1. 大盘指标与趋势
  "GET metrics/summary": () => ({ status: "ok", data: mockMetricsSummary }),
  "GET metrics/trends": () => ({ status: "ok", data: mockAnalyticsTrends }),

  // 2. 活跃任务与控制
  "GET tasks/active": () => ({ status: "ok", data: mockActiveTasks }),
  "GET platforms": () => ({ status: "ok", data: mockConnectedPlatforms }),
  "POST tasks/trigger": () => ({
    status: "ok",
    data: { trace_id: `trace-manual-${Date.now()}`, message: "任务已成功提交排队" },
  }),
  "POST tasks/cancel": () => ({ status: "ok", data: { success: true } }),
  "POST tasks/:traceId/resume": () => ({
    status: "ok",
    data: { trace_id: `trace-resume-${Date.now()}`, message: "任务恢复执行成功" },
  }),

  // 3. 链路追踪
  "GET traces": (params?: Record<string, unknown>) => {
    let items = [...mockTraces];
    if (params?.status && typeof params.status === "string" && params.status !== "ALL") {
      items = items.filter((t) => t.status === params.status);
    }
    if (params?.group_id && typeof params.group_id === "string") {
      items = items.filter((t) => t.group_id.includes(params.group_id as string));
    }
    return {
      status: "ok",
      data: { items, total: items.length },
    };
  },
  "GET traces/:traceId": (params?: Record<string, unknown>, pathParams?: Record<string, string>) => {
    const traceId = pathParams?.traceId || (params?.traceId as string);
    const item = mockTraces.find((t) => t.trace_id === traceId) || mockTraces[0];
    return { status: "ok", data: item };
  },
  "GET groups": () => ({
    status: "ok",
    data: ["123456789", "987654321", "-1001234567890"],
  }),
  "GET providers": () => ({ status: "ok", data: mockProviders }),
  "GET personas": () => ({ status: "ok", data: mockPersonas }),

  // 4. 历史报告与海报模板
  "GET reports/history": () => ({ status: "ok", data: mockReportHistory }),
  "GET reports/content": () => ({
    status: "ok",
    data: {
      ...mockReportHistory[0],
      base64_content:
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='400' height='200'><rect width='100%' height='100%' fill='%231677ff'/><text x='50%' y='50%' fill='white' font-size='20' text-anchor='middle'>Mock Report Preview</text></svg>",
    },
  }),
  "GET reports/templates": () => ({ status: "ok", data: mockReportTemplates }),
  "GET templates/preview": () => ({
    status: "ok",
    data: {
      data_url:
        "data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='300' height='150'><rect width='100%' height='100%' fill='%2352c41a'/><text x='50%' y='50%' fill='white' font-size='16' text-anchor='middle'>Template Preview</text></svg>",
    },
  }),
  "POST templates/install_from_url": () => ({
    status: "ok",
    data: { success: true, message: "模板安装成功", template_name: "custom_demo" },
  }),
  "POST templates/install_from_file": () => ({
    status: "ok",
    data: { success: true, message: "模板上传成功", template_name: "custom_uploaded" },
  }),
  "POST templates/uninstall": () => ({
    status: "ok",
    data: { name: "custom_demo", removed: true },
  }),
  "POST reports/rerender": () => ({
    status: "ok",
    data: {
      success: true,
      filename: "report_rerendered.png",
      report_path: "reports/report_rerendered.png",
      is_html: false,
    },
  }),

  // 5. 日志流
  "GET logs": () => ({ status: "ok", data: mockPluginLogs }),

  // 6. 配置项
  "GET config": () => ({ status: "ok", data: mockPluginConfig }),
  "POST config": (body?: unknown) => ({
    status: "ok",
    data: { success: true, saved: body },
    message: "配置保存成功",
  }),
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
  "POST plugin-data/:section/clear": () => ({ status: "ok", data: { deleted: 10 } }),
  "GET data/incremental/groups": () => ({
    status: "ok",
    data: { groups: ["123456789", "987654321"] },
  }),
  "GET data/incremental/batches": () => ({ status: "ok", data: mockIncrementalBatches }),
  "GET data/incremental/batch/detail": () => ({
    status: "ok",
    data: mockIncrementalBatches.batches[0],
  }),
  "POST data/incremental/batch": () => ({ status: "ok", data: { deleted: true } }),
  "POST data/incremental/reset": () => ({
    status: "ok",
    data: { deleted_batches: 2, message: "已重置增量状态" },
  }),
  "GET data/checkpoints/groups": () => ({
    status: "ok",
    data: { groups: ["123456789"] },
  }),
  "GET data/checkpoints": () => ({ status: "ok", data: mockCheckpoints }),
  "GET data/checkpoint/detail": () => ({
    status: "ok",
    data: {
      detail: {
        ...mockCheckpoints.items[0],
        payload: { sample: "Checkpoint Context Snapshot Data" },
      },
    },
  }),
  "POST data/checkpoint": () => ({ status: "ok", data: { deleted: true } }),
};
