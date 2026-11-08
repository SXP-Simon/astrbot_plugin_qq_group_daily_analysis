import { describe, expect, it } from "vitest";
import { getDefaultThemeColors, getHostThemeStyles, HOST_THEME_PROPERTIES } from "../themeColors";

describe("宿主主题变量", () => {
  it.each([
    undefined,
    null,
    [],
    "#123456",
    {},
    { primary: 12, secondary: {} },
    { primary: "var(--warning)", secondary: "transparent" },
    { primary: "#1234", secondary: "linear-gradient(red, blue)" },
  ])("无效或缺失配色不覆盖 CSS 默认值 %j", (value) => {
    expect(getHostThemeStyles(value, false)).toEqual({});
  });
  it("独立校验两种颜色，支持宿主十六进制、RGB、HSL 和命名颜色", () => {
    for (const primary of [" #fff ", "rgb(255, 255, 255)", "hsl(0, 0%, 100%)", "white"]) {
      expect(getHostThemeStyles({ primary, secondary: "bad-color" }, false)).toMatchObject({
        "--primary": "rgb(255, 255, 255)",
        "--primary-foreground": "#000000",
      });
    }
    expect(getHostThemeStyles({ primary: "invalid", secondary: "#123456" }, true)).toEqual({
      "--secondary": "color-mix(in srgb, rgb(18, 52, 86) 14%, var(--background))",
      "--secondary-color": "rgb(18, 52, 86)",
      "--chart-output": "rgba(18, 52, 86, 0.62)",
      "--chart-trend-output": "rgb(18, 52, 86)",
    });
    expect(getHostThemeStyles({ primary: "black" }, true)["--primary-foreground"]).toBe("#ffffff");
  });
  it("深浅模式调整焦点和图表颜色，不接管警告、错误和成功语义色", () => {
    const palette = { primary: "#123456", secondary: "#987654" };
    const light = getHostThemeStyles(palette, false);
    const dark = getHostThemeStyles(palette, true);
    expect(light["--ring"]).not.toBe(dark["--ring"]);
    expect(light["--chart-input"]).toBe("rgba(18, 52, 86, 0.62)");
    expect(Object.keys(light).sort()).toEqual([...HOST_THEME_PROPERTIES].sort());
    for (const name of ["--warning", "--destructive", "--success", "--info", "--creative"])
      expect(light).not.toHaveProperty(name);
  });
});

it("读取当前主题的默认配置，不受正在生效的宿主覆盖干扰", () => {
  const root = document.documentElement.style;
  root.setProperty("--default-primary", "#123abc");
  root.setProperty("--default-secondary", "#abc123");
  root.setProperty("--primary", "#fedcba");
  try {
    expect(getDefaultThemeColors()).toEqual({ primary: "#123abc", secondary: "#abc123" });
    root.setProperty("--default-primary", "#abcdef");
    expect(getDefaultThemeColors().primary).toBe("#abcdef");
  } finally {
    root.removeProperty("--default-primary");
    root.removeProperty("--default-secondary");
    root.removeProperty("--primary");
  }
});
