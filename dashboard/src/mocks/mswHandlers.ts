import { mockHandlers, type MockHandlerResponse } from "./handlers";

export interface MswHandlerDefinition {
  method: "GET" | "POST" | "DELETE" | "PUT" | "PATCH";
  path: string;
  urlPattern: string;
  resolver: (req: {
    params?: Record<string, string>;
    query?: Record<string, string>;
    body?: unknown;
  }) => MockHandlerResponse;
}

/**
 * 将内部注册的 mockHandlers 转换为声明式的 MSW 兼容 Handler 规范列表。
 * 可直接与 msw 的 `http.get`, `http.post`, `http.delete` 或 Vitest/Playwright 绑定。
 */
export function createMswHandlerDefinitions(
  basePrefix = "/api/plugins/astrbot_plugin_qq_group_daily_analysis"
): MswHandlerDefinition[] {
  const definitions: MswHandlerDefinition[] = [];

  for (const [routeKey, handler] of Object.entries(mockHandlers)) {
    const [method, routePath] = routeKey.split(" ");
    if (!method || !routePath) continue;

    // 格式化为 MSW 识别的标准路径
    const normalizedPath = routePath.startsWith("/") ? routePath.slice(1) : routePath;
    const fullPattern = `${basePrefix}/${normalizedPath}`;

    definitions.push({
      method: method as MswHandlerDefinition["method"],
      path: normalizedPath,
      urlPattern: fullPattern,
      resolver: (req) => {
        return handler(
          (req.query || req.body) as Record<string, unknown> | undefined,
          req.params
        ) as MockHandlerResponse;
      },
    });
  }

  return definitions;
}

/**
 * 预构建的 MSW Handler 规范集合
 */
export const mswHandlerDefinitions = createMswHandlerDefinitions();
