import { ApiResponse, AstrBotContext, SSEEventWrapper } from "./bridge";
import { mockHandlers, mockSSEService } from "../../mocks";

const PLUGIN_BASE_PATH = "/api/plugins/astrbot_plugin_qq_group_daily_analysis";

export type DevBridgeMode = "mock" | "proxy";

export function getDevBridgeMode(): DevBridgeMode {
  if (typeof window === "undefined") return "mock";
  try {
    const urlParam = new URLSearchParams(window.location.search).get("devMode");
    if (urlParam === "proxy" || urlParam === "mock") {
      return urlParam;
    }
    if (window.localStorage && typeof window.localStorage.getItem === "function") {
      return (window.localStorage.getItem("astrbot_dev_bridge_mode") as DevBridgeMode) || "mock";
    }
  } catch {
    // ignore
  }
  return "mock";
}

export function setDevBridgeMode(mode: DevBridgeMode) {
  if (typeof window !== "undefined") {
    try {
      if (window.localStorage && typeof window.localStorage.setItem === "function") {
        window.localStorage.setItem("astrbot_dev_bridge_mode", mode);
      }
    } catch {
      // ignore
    }
    window.location.reload();
  }
}

/**
 * 将路由与参数解析分发至 Mock Handlers
 */
function matchMockHandler(method: string, path: string, params?: Record<string, unknown>, body?: unknown) {
  const cleanPath = path.replace(/^\/+/, "");
  const targetKey = `${method.toUpperCase()} ${cleanPath}`;

  // 1. 精确匹配
  if (targetKey in mockHandlers) {
    const handler = mockHandlers[targetKey as keyof typeof mockHandlers];
    return handler(params || (body as Record<string, unknown>));
  }

  // 2. 动态参数模式匹配 (如 traces/:traceId, tasks/:traceId/resume, plugin-data/:section/clear)
  for (const [pattern, handler] of Object.entries(mockHandlers)) {
    const [hMethod, hPath] = pattern.split(" ");
    if (hMethod !== method.toUpperCase()) continue;

    const patternParts = hPath.split("/");
    const pathParts = cleanPath.split("/");

    if (patternParts.length === pathParts.length) {
      const pathParams: Record<string, string> = {};
      let match = true;

      for (let i = 0; i < patternParts.length; i++) {
        if (patternParts[i].startsWith(":")) {
          const paramName = patternParts[i].slice(1);
          pathParams[paramName] = pathParts[i];
        } else if (patternParts[i] !== pathParts[i]) {
          match = false;
          break;
        }
      }

      if (match) {
        return handler(params || (body as Record<string, unknown>), pathParams);
      }
    }
  }

  return { status: "ok", data: null, message: `No mock handler matched for [${targetKey}]` };
}

export async function devFetchContext(): Promise<AstrBotContext> {
  return {
    isDark: false,
    pluginName: "astrbot_plugin_qq_group_daily_analysis",
    version: "v5.6.4",
  };
}

export async function devApiGet<T = unknown>(
  path: string,
  params?: Record<string, unknown>
): Promise<ApiResponse<T> | null> {
  const mode = getDevBridgeMode();
  if (mode === "proxy") {
    try {
      const search = params ? `?${new URLSearchParams(params as Record<string, string>).toString()}` : "";
      const res = await fetch(`${PLUGIN_BASE_PATH}/${path.replace(/^\/+/, "")}${search}`);
      return (await res.json()) as ApiResponse<T>;
    } catch (err) {
      console.error(`[DevBridge Proxy GET Error] ${path}:`, err);
      return null;
    }
  }

  // 模拟异步网络延迟 (30ms ~ 100ms)
  await new Promise((resolve) => setTimeout(resolve, 50));
  const res = matchMockHandler("GET", path, params);
  return res as ApiResponse<T>;
}

export async function devApiPost<T = unknown>(
  path: string,
  body?: unknown
): Promise<ApiResponse<T> | null> {
  const mode = getDevBridgeMode();
  if (mode === "proxy") {
    try {
      const res = await fetch(`${PLUGIN_BASE_PATH}/${path.replace(/^\/+/, "")}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body || {}),
      });
      return (await res.json()) as ApiResponse<T>;
    } catch (err) {
      console.error(`[DevBridge Proxy POST Error] ${path}:`, err);
      return null;
    }
  }

  // 模拟异步网络延迟
  await new Promise((resolve) => setTimeout(resolve, 50));
  const res = matchMockHandler("POST", path, undefined, body);
  return res as ApiResponse<T>;
}

export function devSubscribeSSE(handlers: {
  onMessage: (event: SSEEventWrapper) => void;
  onError?: () => void;
}): (() => void) | null {
  const mode = getDevBridgeMode();
  if (mode === "proxy") {
    try {
      const es = new EventSource(`${PLUGIN_BASE_PATH}/events/stream`);
      es.onmessage = (evt) => {
        try {
          const parsed = JSON.parse(evt.data);
          handlers.onMessage({ parsed, raw: evt.data });
        } catch {
          handlers.onMessage({ raw: evt.data });
        }
      };
      es.onerror = () => {
        handlers.onError?.();
      };
      return () => es.close();
    } catch (err) {
      console.error("[DevBridge Proxy SSE Error]:", err);
      return null;
    }
  }

  return mockSSEService.subscribe({
    onMessage: (evt) => handlers.onMessage({ parsed: evt }),
    onError: handlers.onError,
  });
}
