import { useEffect, useState } from "react";
import { fetchContext, AstrBotContext } from "../api/bridge";

const THEME_CACHE_KEY = "astrbot_plugin_theme_is_dark";

function getInitialTheme(): boolean {
  try {
    // 1. 优先从 URL 参数中直接获取（最权威且无时延，AstrBot iframe 路由必带 ?theme=dark / light）
    if (typeof window !== "undefined" && window.location) {
      const params = new URLSearchParams(window.location.search);
      const themeVal = params.get("theme");
      const isDarkParam = params.get("isDark");

      if (themeVal === "dark" || isDarkParam === "true") {
        return true;
      }
      if (themeVal === "light" || isDarkParam === "false") {
        return false;
      }
    }

    // 2. 从本地持久化缓存中恢复
    if (typeof localStorage !== "undefined") {
      const cached = localStorage.getItem(THEME_CACHE_KEY);
      if (cached !== null) {
        return cached === "true";
      }
    }

    // 3. 尝试读取父级窗口 (AstrBot Host) document 属性或暗色 class
    try {
      if (window.parent && window.parent.document) {
        const parentHtml = window.parent.document.documentElement;
        if (
          parentHtml.classList.contains("dark") ||
          parentHtml.getAttribute("data-theme") === "dark" ||
          window.parent.document.body.classList.contains("dark")
        ) {
          return true;
        }
      }
    } catch {
      // 跨域 iframe 安全拦截，忽略
    }
  } catch {
    // 忽略异常
  }
  return false;
}

// 全局单例主题状态与多组件订阅总线（杜绝各组件独立 useState 状态失步与竞态）
let globalIsDark: boolean = getInitialTheme();
const listeners = new Set<(val: boolean) => void>();

function updateGlobalTheme(newVal: boolean) {
  if (globalIsDark !== newVal) {
    globalIsDark = newVal;
    try {
      localStorage.setItem(THEME_CACHE_KEY, String(newVal));
    } catch {
      // 忽略存储异常
    }
    listeners.forEach((fn) => fn(newVal));
  }
}

// 统一由全局通信单例监听 AstrBot Host 事件
if (typeof window !== "undefined") {
  fetchContext().then((ctx) => {
    if (ctx?.isDark !== undefined) {
      updateGlobalTheme(!!ctx.isDark);
    }
  });

  const bridge = window.AstrBotPluginPage;
  if (bridge && typeof bridge.onContext === "function") {
    bridge.onContext((ctx: AstrBotContext) => {
      if (ctx?.isDark !== undefined) {
        updateGlobalTheme(!!ctx.isDark);
      }
    });
  }
}

/**
 * 监听 AstrBot 宿主暗黑模式状态 Hook (Shared Theme Hook)
 * 全局单例响应式同步，杜绝任何页面与抽屉组件的状态割裂
 */
export function useTheme() {
  const [isDark, setIsDark] = useState<boolean>(globalIsDark);

  useEffect(() => {
    // 挂载时立即校准为全局最新状态
    setIsDark(globalIsDark);
    const handler = (val: boolean) => setIsDark(val);
    listeners.add(handler);
    return () => {
      listeners.delete(handler);
    };
  }, []);

  return { isDark };
}
