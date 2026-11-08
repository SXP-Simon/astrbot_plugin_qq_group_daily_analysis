import { z } from "zod";
import type { AstrBotContext } from "./bridge";

const STORAGE_KEY = "astrbot_dev_theme_context";
const contextSchema = z.object({
  isDark: z.boolean().optional(),
  themeColors: z.object({ primary: z.string(), secondary: z.string() }).optional(),
});
export type DevThemeContext = z.infer<typeof contextSchema>;
const listeners = new Set<(context: AstrBotContext) => void>();

export function getDevThemeContext(): DevThemeContext {
  try {
    const result = contextSchema.safeParse(JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}"));
    return result.success ? result.data : {};
  } catch {
    return {};
  }
}

export function setDevThemeContext(context: DevThemeContext): void {
  const next = contextSchema.parse(context);
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* 存储受限时仍允许本次预览。 */
  }
  listeners.forEach((listener) => listener(next));
}

export function devSubscribeContext(callback: (context: AstrBotContext) => void): () => void {
  listeners.add(callback);
  callback(getDevThemeContext());
  return () => {
    listeners.delete(callback);
  };
}
