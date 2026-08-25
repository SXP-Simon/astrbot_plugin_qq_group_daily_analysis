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
  return null;
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
  return null;
}
