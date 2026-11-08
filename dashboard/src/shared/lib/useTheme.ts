import { useEffect, useState } from "react";
import { fetchContext, subscribeContext, type AstrBotContext } from "../api/bridge";
import { getHostThemeStyles, HOST_THEME_PROPERTIES } from "./themeColors";

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

// 颜色变化也生成新快照，让只订阅主题的图表在深浅模式不变时更新。
let globalTheme = { isDark: getInitialTheme(), revision: 0 };
let appliedStyles = "";
const listeners = new Set<(theme: typeof globalTheme) => void>();

function updateGlobalTheme(context: AstrBotContext) {
  const isDark = typeof context.isDark === "boolean" ? context.isDark : globalTheme.isDark;
  document.documentElement.classList.toggle("dark", isDark);
  document.documentElement.dataset.theme = isDark ? "dark" : "light";
  const styles = getHostThemeStyles(context.themeColors, isDark);
  for (const property of HOST_THEME_PROPERTIES) {
    if (styles[property]) document.documentElement.style.setProperty(property, styles[property]);
    else document.documentElement.style.removeProperty(property);
  }
  const styleKey = JSON.stringify(styles);
  if (isDark === globalTheme.isDark && styleKey === appliedStyles) return;
  if (isDark !== globalTheme.isDark) {
    try {
      localStorage.setItem(THEME_CACHE_KEY, String(isDark));
    } catch {
      /* 沙盒可能禁用存储。 */
    }
  }
  appliedStyles = styleKey;
  globalTheme = { isDark, revision: globalTheme.revision + 1 };
  listeners.forEach((listener) => listener(globalTheme));
}

if (typeof window !== "undefined") {
  updateGlobalTheme({ isDark: globalTheme.isDark });
  let receivedContext = false;
  fetchContext()
    .then((context) => {
      // 任何较新的上下文通知都优先于迟到的初始化快照，包括只更新颜色的通知。
      if (!receivedContext) updateGlobalTheme(context);
    })
    .catch(() => {
      /* 保留 URL、缓存主题及 CSS 默认配色。 */
    });
  const unsubscribe = subscribeContext((context) => {
    receivedContext = true;
    updateGlobalTheme(context);
  });
  if (import.meta.hot) import.meta.hot.dispose(unsubscribe);
}

/** 订阅宿主深浅模式和配色变化，页面、图表和 Portal 弹层共用同一主题。 */
export function useTheme() {
  const [theme, setTheme] = useState(globalTheme);
  useEffect(() => {
    setTheme(globalTheme);
    listeners.add(setTheme);
    return () => {
      listeners.delete(setTheme);
    };
  }, []);
  return theme;
}
