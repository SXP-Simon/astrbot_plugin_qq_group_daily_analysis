import { afterEach, expect, it, vi } from "vitest";
import { color } from "echarts/core";
import { resolveChartColor } from "@/shared/lib/chartColors";

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

it.each(["#3c96ca", "rgb(30, 75, 101)", "rgba(47, 134, 189, 0.62)"])(
  "ECharts 已支持的颜色不经过画布转换：%s",
  (value) => {
    const canvas = vi.spyOn(HTMLCanvasElement.prototype, "getContext");
    expect(resolveChartColor(value)).toBe(value);
    expect(canvas).not.toHaveBeenCalled();
    expect(color.lift(resolveChartColor(value), -0.1)).toBeTruthy();
  },
);

it.each([
  "color-mix(in srgb, #3c96ca 50%, #000)",
  "color(srgb 0.12 0.3 0.4 / 0.62)",
  "oklch(45% 0.1 220)",
])("浏览器颜色转换后可参与高亮运算且保留透明度：%s", (value) => {
  vi.stubGlobal("CSS", { supports: vi.fn(() => true) });
  const context = {
    fillStyle: "",
    fillRect: vi.fn(),
    getImageData: vi.fn(() => ({ data: new Uint8ClampedArray([30, 75, 101, 158]) })),
  };
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
    context as unknown as CanvasRenderingContext2D,
  );
  expect(color.parse(value)).toBeUndefined();
  const resolved = resolveChartColor(value);
  expect(context.fillStyle).toBe(value);
  expect(context.fillRect).toHaveBeenCalledWith(0, 0, 1, 1);
  expect(color.parse(resolved)).toEqual([30, 75, 101, 158 / 255]);
  expect(color.lift(resolved, -0.1)).toBeTruthy();
});

it("未知、缺失或无法读取的颜色回退到可解析值", () => {
  vi.stubGlobal("CSS", { supports: vi.fn(() => false) });
  expect(resolveChartColor("invalid", "#123456")).toBe("#123456");
  expect(resolveChartColor("", "invalid")).toBe("#64748b");
  expect(resolveChartColor("currentColor", "rgb(10, 20, 30)")).toBe("rgb(10, 20, 30)");
  vi.stubGlobal("CSS", { supports: vi.fn(() => true) });
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  expect(resolveChartColor("color-mix(in srgb, blue 50%, white)", "#123456")).toBe("#123456");
});
