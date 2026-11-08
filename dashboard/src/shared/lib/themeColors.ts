import { color } from "echarts/core";
import { z } from "zod";

export const HOST_THEME_PROPERTIES = [
  "--primary",
  "--primary-foreground",
  "--accent",
  "--ring",
  "--secondary",
  "--secondary-color",
  "--chart-input",
  "--chart-output",
  "--chart-trend-input",
  "--chart-trend-output",
] as const;

/** 校验宿主配色并生成有限的主题覆盖；缺失、无效或透明颜色交给原 CSS 兜底。 */
export function getHostThemeStyles(value: unknown, isDark: boolean): Record<string, string> {
  const result = z
    .object({ primary: z.unknown().optional(), secondary: z.unknown().optional() })
    .safeParse(value);
  const styles: Record<string, string> = {};
  if (!result.success) return styles;
  for (const key of ["primary", "secondary"] as const) {
    const raw = result.data[key];
    if (typeof raw !== "string" || raw.length > 128) continue;
    const rgb = color.parse(raw.trim());
    if (!rgb || rgb.length !== 4 || rgb.some((part) => !Number.isFinite(part)) || rgb[3] !== 1)
      continue;
    const [r, g, b] = rgb;
    const css = `rgb(${r}, ${g}, ${b})`;
    if (key === "primary") {
      const luminance = rgb.slice(0, 3).reduce((sum, channel, index) => {
        const linear = channel / 255;
        return (
          sum +
          (linear <= 0.04045 ? linear / 12.92 : ((linear + 0.055) / 1.055) ** 2.4) *
            [0.2126, 0.7152, 0.0722][index]
        );
      }, 0);
      styles["--primary"] = css;
      // 黑白前景择取较高对比度，避免浅色按钮仍使用白字。
      styles["--primary-foreground"] =
        (luminance + 0.05) / 0.05 >= 1.05 / (luminance + 0.05) ? "#000000" : "#ffffff";
      styles["--accent"] = `color-mix(in srgb, ${css} 14%, var(--background))`;
      styles["--ring"] = `rgb(${rgb
        .slice(0, 3)
        .map((channel) => Math.round((channel + (isDark ? 255 : 0)) / 2))
        .join(", ")})`;
      styles["--chart-input"] = `rgba(${r}, ${g}, ${b}, 0.62)`;
      styles["--chart-trend-input"] = css;
    } else {
      // 辅助色以低饱和底色参与按钮与选区，正文和状态语义不随之改写。
      styles["--secondary"] = `color-mix(in srgb, ${css} 14%, var(--background))`;
      styles["--secondary-color"] = css;
      styles["--chart-output"] = `rgba(${r}, ${g}, ${b}, 0.62)`;
      styles["--chart-trend-output"] = css;
    }
  }
  return styles;
}
