import {
  devApiGet,
  devApiPost,
  devApiUpload,
  devFetchContext,
  devSubscribeSSE,
} from "./devBridge";

/**
 * AstrBot 插件 Page Bridge 通信底层 (Shared API Bridge)
 * 严格类型定义，杜绝无意义的 any 类型
 */

export interface AstrBotContext {
  isDark?: boolean;
  pluginName?: string;
  [key: string]: unknown;
}

export interface SSEEventWrapper {
  parsed?: unknown;
  raw?: string;
}

export interface ApiResponse<T = unknown> {
  status?: string;
  data?: T;
  message?: string;
  items?: T extends Array<infer U> ? U[] : unknown[];
  total?: number;
  [key: string]: unknown;
}

export interface AstrBotPluginPageBridge {
  upload?: <T = unknown>(path: string, file: File) => Promise<ApiResponse<T> | null>;
  ready: () => Promise<AstrBotContext>;
  onContext?: (callback: (ctx: AstrBotContext) => void) => () => void;
  apiGet: <T = unknown>(
    path: string,
    params?: Record<string, unknown>
  ) => Promise<ApiResponse<T> | null>;
  apiPost: <T = unknown>(
    path: string,
    body?: unknown
  ) => Promise<ApiResponse<T> | null>;
  subscribeSSE: (
    path: string,
    handlers: {
      onMessage: (evt: SSEEventWrapper) => void;
      onError?: () => void;
    }
  ) => Promise<string | number>;
  unsubscribeSSE: (subscriptionId: string | number) => void;
}

declare global {
  interface Window {
    AstrBotPluginPage?: AstrBotPluginPageBridge;
  }
}

/** 使用宿主二进制上传能力，避免大文件膨胀为 Base64 JSON。 */
export async function apiUpload(path: string, file: File): Promise<unknown> {
  const bridge = getBridge();
  let response: unknown;
  let pending: Promise<unknown>;
  if (bridge) {
    if (typeof bridge.upload !== "function") throw new Error("当前宿主不支持二进制文件上传，请升级 AstrBot 后重试。");
    pending = bridge.upload(path, file);
  } else if (import.meta.env.DEV) pending = devApiUpload(path, file);
  else throw new Error("宿主上传接口不可用");
  let timer: ReturnType<typeof setTimeout> | undefined;
  try {
    // 与宿主 files:upload 的 60 秒上限一致；失败后业务层会请求后端取消并清理。
    response = await Promise.race([pending, new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error("上传分块超过 60 秒未收到回执，将停止后续传输并清理暂存；请检查到插件服务器的连接。")), 60_000);
    })]);
  } finally { clearTimeout(timer); }
  if (!response) throw new Error("未收到上传回执，请检查连接并刷新文件状态。");
  extractData(response);
  return response;
}

function getBridge(): AstrBotPluginPageBridge | null {
  return window.AstrBotPluginPage || null;
}

export async function fetchContext(): Promise<AstrBotContext> {
  const bridge = getBridge();
  if (bridge && typeof bridge.ready === "function") {
    return await bridge.ready();
  }
  if (import.meta.env.DEV) {
    return await devFetchContext();
  }
  return { isDark: false, pluginName: "astrbot_plugin_qq_group_daily_analysis" };
}

export async function apiGet<T = unknown>(
  path: string,
  params?: Record<string, unknown>
): Promise<ApiResponse<T> | null> {
  const bridge = getBridge();
  let response: ApiResponse<T> | null = null;
  if (bridge && typeof bridge.apiGet === "function") {
    response = await bridge.apiGet<T>(path, params);
  } else if (import.meta.env.DEV) {
    response = await devApiGet<T>(path, params);
  }
  if (!response) throw new Error("未收到接口响应，请检查连接后重试。");
  extractData(response);
  return response;
}

export async function apiPost<T = unknown>(
  path: string,
  body?: unknown
): Promise<ApiResponse<T> | null> {
  const bridge = getBridge();
  let response: ApiResponse<T> | null = null;
  if (bridge && typeof bridge.apiPost === "function") {
    response = await bridge.apiPost<T>(path, body);
  } else if (import.meta.env.DEV) {
    response = await devApiPost<T>(path, body);
  }
  if (!response) throw new Error("未收到接口响应，请检查连接后重试。");
  extractData(response);
  return response;
}

export function subscribeSSE(handlers: {
  onMessage: (event: unknown) => void;
  onError?: () => void;
}): (() => void) | null {
  const bridge = getBridge();
  if (bridge && typeof bridge.subscribeSSE === "function") {
    let subId: string | number | null = null;
    bridge
      .subscribeSSE("events/stream", {
        onMessage: (evt: SSEEventWrapper) => {
          const payload = evt.parsed !== undefined ? evt.parsed : evt.raw;
          handlers.onMessage(payload);
        },
        onError: handlers.onError,
      })
      .then((id) => {
        subId = id;
      });

    return () => {
      if (subId !== null && typeof bridge.unsubscribeSSE === "function") {
        bridge.unsubscribeSSE(subId);
      }
    };
  }
  if (import.meta.env.DEV) {
    return devSubscribeSSE({
      onMessage: (evt) => {
        const payload = evt.parsed !== undefined ? evt.parsed : evt.raw;
        handlers.onMessage(payload);
      },
      onError: handlers.onError,
    });
  }
  return null;
}

/**
 * 仅解包响应信封，保留业务对象的 data，并拒绝任一层的错误回执。
 */
export function extractData<T>(res: unknown): T | null {
  if (!res || typeof res !== "object") return null;
  let current: unknown = res;
  for (let depth = 0; depth < 3; depth += 1) {
    if (!current || typeof current !== "object" || Array.isArray(current)) break;
    const layer = current as Record<string, unknown>;
    // 记录、快照等业务对象也有 data；存在业务字段时保留整个对象。
    if (!Object.keys(layer).every(key => ["status", "code", "message", "error", "data", "status_code", "headers"].includes(key))) break;
    if (layer.status === "error" || layer.error ||
        (typeof layer.code === "number" && ![0, 200].includes(layer.code)) ||
        (typeof layer.status_code === "number" && layer.status_code >= 400)) {
      throw new Error(typeof layer.message === "string" && layer.message ? layer.message : "接口操作失败，请刷新后重试。");
    }
    if (layer.data === undefined) break;
    current = layer.data;
  }
  return current as T | null;
}

