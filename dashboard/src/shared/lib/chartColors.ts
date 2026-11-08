import { color } from "echarts/core";

/** 将浏览器支持的主题色转换为 ECharts 高亮计算也能解析的颜色，保留透明度。 */
export function resolveChartColor(value: string, fallback = "#64748b"): string {
  const raw = value.trim();
  if (color.parse(raw)) return raw;
  // CSS 变量计算后仍可能是 color-mix、color(srgb ...) 或 OKLCH；SVG 能显示，
  // ECharts 5 的自动高亮却无法解析。通过 sRGB 像素读取统一格式，不改页面主题。
  if (
    raw &&
    raw.toLowerCase() !== "currentcolor" &&
    typeof CSS !== "undefined" &&
    CSS.supports("color", raw)
  ) {
    const canvas = document.createElement("canvas");
    canvas.width = canvas.height = 1;
    const context = canvas.getContext("2d", { willReadFrequently: true });
    if (context) {
      context.fillStyle = raw;
      context.fillRect(0, 0, 1, 1);
      const [r, g, b, a] = context.getImageData(0, 0, 1, 1).data;
      return `rgba(${r}, ${g}, ${b}, ${a / 255})`;
    }
  }
  return color.parse(fallback) ? fallback : "#64748b";
}
