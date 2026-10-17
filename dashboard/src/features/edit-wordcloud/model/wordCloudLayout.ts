import { DEFAULT_WORDCLOUD_OPTIONS, type WordCloudOptions } from "../../../entities/wordcloud/model/types";

export const VISUAL_FIELDS = ["font", "min_font_size", "max_font_size", "max_words", "word_spacing", "width", "height", "rotation", "palette"] as const;
export type DensityPreset = "compact" | "balanced" | "spacious";
export const DENSITY_PRESETS: Record<DensityPreset, Record<string, number>> = {
  compact: { min_font_size: 24, max_font_size: 72, max_words: 120, word_spacing: 3 },
  balanced: { min_font_size: 34, max_font_size: 90, max_words: 80, word_spacing: 10 },
  spacious: { min_font_size: 40, max_font_size: 100, max_words: 50, word_spacing: 18 },
};

/** 只提取外观字段，保护发送规则、统计规则及群级覆盖。 */
export function visualPatch(options: Record<string, unknown>) {
  return Object.fromEntries(VISUAL_FIELDS.filter((key) => options[key] !== undefined).map((key) => [key, options[key]]));
}

/** 字段独立回退只用于无法显示的类型，合法类型中的错误输入仍原样展示。 */
export function readableDraft(value: Record<string, unknown> | undefined): WordCloudOptions {
  const draft: Record<string, unknown> = { ...DEFAULT_WORDCLOUD_OPTIONS, ...value };
  for (const [key, fallback] of Object.entries(DEFAULT_WORDCLOUD_OPTIONS)) {
    const raw = draft[key];
    if (Array.isArray(fallback)) {
      if (!Array.isArray(raw) || !raw.every((item: unknown) => typeof item === "string")) draft[key] = fallback;
    } else if (typeof raw !== typeof fallback) draft[key] = fallback;
  }
  return draft as WordCloudOptions;
}

/** 最多尝试四轮，优先收紧间距，再降低字号，字号不低于初始值的 75%。 */
export function fitCandidates(options: WordCloudOptions): WordCloudOptions[] {
  const candidates = [
    { word_spacing: Math.floor(options.word_spacing * 0.5) },
    { word_spacing: 0 },
    { word_spacing: 0, min_font_size: Math.max(12, Math.floor(options.min_font_size * 0.88)), max_font_size: Math.max(12, Math.floor(options.max_font_size * 0.88)) },
    { word_spacing: 0, min_font_size: Math.max(12, Math.floor(options.min_font_size * 0.75)), max_font_size: Math.max(12, Math.floor(options.max_font_size * 0.75)) },
  ].map((patch) => ({ ...options, ...patch }));
  const seen = new Set([JSON.stringify(options)]);
  return candidates.filter((candidate) => {
    const key = JSON.stringify(candidate);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export interface RenderCounts { placed: number; total: number }

/** 在沙箱中等待模板的字体、图片与排版就绪事件，读取实际排入词数。 */
export function measureWordCloudHtml(html: string, options: WordCloudOptions, signal: AbortSignal): Promise<RenderCounts> {
  return new Promise((resolve, reject) => {
    if (signal.aborted) { reject(new Error("已取消调整")); return; }
    const frame = document.createElement("iframe");
    frame.setAttribute("sandbox", "allow-scripts");
    frame.setAttribute("aria-hidden", "true");
    frame.tabIndex = -1;
    // 保持在视口内，避免 Chromium 暂停离屏沙箱的动画帧而触发模板超时。
    Object.assign(frame.style, { position: "fixed", top: "0", left: "0", opacity: "0", pointerEvents: "none", zIndex: "-1", width: `${options.width}px`, height: `${options.height}px`, border: "0" });
    const cleanup = () => {
      window.clearTimeout(timer);
      window.removeEventListener("message", onMessage);
      signal.removeEventListener("abort", onAbort);
      frame.remove();
    };
    const onAbort = () => { cleanup(); reject(new Error("已取消调整")); };
    const onMessage = (event: MessageEvent<unknown>) => {
      if (event.source !== frame.contentWindow || !event.data || typeof event.data !== "object") return;
      const data = event.data as Record<string, unknown>;
      if (data.type !== "wordcloud-render-state" && data.type !== "astrbot-wordcloud-ready") return;
      const state = data.state ?? data.status;
      if (state !== "ready" && state !== "error") return;
      const placed = data.shown ?? data.placed;
      cleanup();
      if (state === "error" || typeof placed !== "number" || typeof data.total !== "number") reject(new Error(typeof data.error === "string" && data.error ? data.error : "词云排版未返回有效词数"));
      else resolve({ placed, total: data.total });
    };
    const timer = window.setTimeout(() => { cleanup(); reject(new Error("字体或图片加载超时，请稍后重试")); }, 20000);
    window.addEventListener("message", onMessage);
    signal.addEventListener("abort", onAbort, { once: true });
    frame.srcdoc = html;
    document.body.appendChild(frame);
  });
}
