import { useEffect, useState } from "react";
import { fetchContext, AstrBotContext } from "../api/bridge";

/**
 * 监听 AstrBot 宿主暗黑模式状态 Hook (Shared Theme Hook)
 */
export function useTheme() {
  const [isDark, setIsDark] = useState(false);

  useEffect(() => {
    fetchContext().then((ctx) => {
      if (ctx?.isDark !== undefined) {
        setIsDark(!!ctx.isDark);
      }
    });

    const bridge = window.AstrBotPluginPage;
    if (bridge && typeof bridge.onContext === "function") {
      const off = bridge.onContext((ctx: AstrBotContext) => {
        if (ctx?.isDark !== undefined) {
          setIsDark(!!ctx.isDark);
        }
      });
      return () => off();
    }
  }, []);

  return { isDark };
}
