import {
  devApiGet,
  devApiPost,
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
  upload?: <T = unknown>(path: string, file: File) => Promise<ApiResponse<T> | null>;
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
  if (bridge && typeof bridge.apiGet === "function") {
    return await bridge.apiGet<T>(path, params);
  }
  if (import.meta.env.DEV) {
    return await devApiGet<T>(path, params);
  }
  return null;
}

export async function apiPost<T = unknown>(
  path: string,
  body?: unknown
): Promise<ApiResponse<T> | null> {
  const bridge = getBridge();
  if (bridge && typeof bridge.apiPost === "function") {
    return await bridge.apiPost<T>(path, body);
  }
  if (import.meta.env.DEV) {
    return await devApiPost<T>(path, body);
  }
  return null;
}

/** 通过宿主的文件上传桥接保留鉴权和 multipart 文件内容。 */
export async function apiUpload<T = unknown>(path: string, file: File): Promise<ApiResponse<T> | null> {
  const bridge = getBridge();
  if (bridge?.upload) return bridge.upload<T>(path, file);
  if (import.meta.env.DEV) {
    const body = new FormData();
    body.append("file", file);
    const response = await fetch(`/api/plugins/astrbot_plugin_qq_group_daily_analysis/${path.replace(/^\/+/, "")}`, {
      method: "POST",
      body,
    });
    if (!response.ok) throw new Error(`上传字体失败（${response.status}）`);
    return response.json() as Promise<ApiResponse<T>>;
  }
  throw new Error("当前宿主不支持文件上传，请更新 AstrBot 后重试");
}

interface SSEHandlers {
  onMessage: (event: unknown) => void;
  onError?: () => void;
}

interface SharedHostSubscription {
  listeners: Set<SSEHandlers>;
  id: string | number | null;
  closed: boolean;
}

// 同一插件页面的总览和日志共享一条连接，避免占满 HTTP/1.1 同源连接池。
const hostSubscriptions = new WeakMap<AstrBotPluginPageBridge, SharedHostSubscription>();

export function subscribeSSE(handlers: SSEHandlers): (() => void) | null {
  const bridge = getBridge();
  if (bridge && typeof bridge.subscribeSSE === "function") {
    // 即便重复传入同一 handlers 对象，每次订阅也拥有独立的取消句柄。
    const listener = { ...handlers };
    let subscription = hostSubscriptions.get(bridge);
    const creating = !subscription;
    if (!subscription) {
      subscription = { listeners: new Set(), id: null, closed: false };
      hostSubscriptions.set(bridge, subscription);
    }
    const current = subscription;
    current.listeners.add(listener);

    if (creating) {
      const dispatch = (notify: (subscriber: SSEHandlers) => void) => {
        if (current.closed) return;
        for (const subscriber of [...current.listeners]) {
          if (!current.listeners.has(subscriber)) continue;
          try { notify(subscriber); }
          catch { /* 单个视图处理失败不应打断其他视图的事件分发。 */ }
        }
      };
      const failed = () => {
        if (current.closed) return;
        if (hostSubscriptions.get(bridge) === current) hostSubscriptions.delete(bridge);
        dispatch((subscriber) => subscriber.onError?.());
        current.closed = true;
        current.listeners.clear();
      };
      try {
        void bridge.subscribeSSE("events/stream", {
          onMessage: (evt) => {
            const payload = evt.parsed !== undefined ? evt.parsed : evt.raw;
            dispatch((subscriber) => subscriber.onMessage(payload));
          },
          onError: () => dispatch((subscriber) => subscriber.onError?.()),
        }).then((id) => {
          // 卸载可能早于宿主返回订阅 ID，迟到的连接仍必须立即释放。
          if (current.closed) bridge.unsubscribeSSE(id);
          else current.id = id;
        }).catch(failed);
      } catch {
        failed();
      }
    }

    return () => {
      if (!current.listeners.delete(listener) || current.listeners.size > 0 || current.closed) return;
      current.closed = true;
      if (hostSubscriptions.get(bridge) === current) hostSubscriptions.delete(bridge);
      if (current.id !== null) bridge.unsubscribeSSE(current.id);
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
 * 健壮地解包 AstrBot 插件 Web API 返回的数据结构
 * 兼容 AstrBot 标准响应封装与嵌套 data 结构
 */
export function extractData<T>(res: unknown): T | null {
  if (!res || typeof res !== "object") return null;
  const anyRes = res as Record<string, unknown>;

  // 1. 深度嵌套解包：res.data.data (标准 json_response 经由 AstrBot PageBridge 转发)
  if (
    anyRes.data &&
    typeof anyRes.data === "object" &&
    "data" in (anyRes.data as Record<string, unknown>)
  ) {
    return (anyRes.data as Record<string, unknown>).data as T;
  }

  // 2. 单层解包：res.data
  if (anyRes.data !== undefined) {
    return anyRes.data as T;
  }

  // 3. 顶层对象
  return anyRes as unknown as T;
}

