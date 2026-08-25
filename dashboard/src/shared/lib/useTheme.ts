import { useEffect, useState } from "react";
import { fetchContext, AstrBotContext } from "../api/bridge";

const THEME_CACHE_KEY = "astrbot_plugin_theme_is_dark";

function getInitialTheme(): boolean {
  try {
    // 1. 尝试从 URL 参数中直接获取
    if (typeof window !== "undefined" && window.location) {
      const params = new URLSearchParams(window.location.search);
      if (params.get("theme") === "dark" || params.get("isDark") === "true") {
        return true;
      }
      if (params.get("theme") === "light" || params.get("isDark") === "false") {
        return false;
      }
    }

    // 2. 尝试从本地存储缓存中恢复上次的主题状态（彻底解决切 Tab / 重载时的浅色白色闪烁）
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

    // 4. 兜底匹配系统 prefers-color-scheme
    if (
      typeof window !== "undefined" &&
      window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: dark)").matches
    ) {
      return true;
    }
  } catch {
    // 忽略解析异常
  }
  return false;
}

/**
 * 监听 AstrBot 宿主暗黑模式状态 Hook (Shared Theme Hook)
 * 内置防闪烁同步预读取与本地状态缓存
 */
export function useTheme() {
  const [isDark, setIsDark] = useState<boolean>(getInitialTheme);

  useEffect(() => {
    fetchContext().then((ctx) => {
      if (ctx?.isDark !== undefined) {
        const val = !!ctx.isDark;
        setIsDark(val);
        try {
          localStorage.setItem(THEME_CACHE_KEY, String(val));
        } catch {
          // 忽略 localStorage 存储异常
        }
      }
    });

    const bridge = window.AstrBotPluginPage;
    if (bridge && typeof bridge.onContext === "function") {
      const off = bridge.onContext((ctx: AstrBotContext) => {
        if (ctx?.isDark !== undefined) {
          const val = !!ctx.isDark;
          setIsDark(val);
          try {
            localStorage.setItem(THEME_CACHE_KEY, String(val));
          } catch {
            // 忽略 localStorage 存储异常
          }
        }
      });
      return () => off();
    }
  }, []);

  return { isDark };
}
