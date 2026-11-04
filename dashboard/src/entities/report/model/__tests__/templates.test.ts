import { describe, expect, it } from "vitest";
import { getTemplateCdnUrl, supportsTemplate, templateCapabilities } from "../templates";

describe("模板预览使用配置模块校验后的地址", () => {
  it("拼接已规范化的 CDN 根地址", () => {
    expect(getTemplateCdnUrl("HatsuneMiku", "https://fastly.jsdelivr.net")).toBe(
      "https://fastly.jsdelivr.net/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@main/assets/HatsuneMiku-demo.webp",
    );
  });
  it("配置无效时不生成远程地址，不偷偷替换默认站点", () => {
    expect(getTemplateCdnUrl("maria", null)).toBeUndefined();
  });
});

const html = { id: "web", label: "网页", has_image: true, has_html: true, has_typst: false };
const native = { id: "native", label: "原生", has_image: false, has_html: false, has_typst: true };

describe("模板入口能力", () => {
  it("图片按实际引擎过滤，不把 HTML 图片能力当作 Typst", () => {
    expect(supportsTemplate(html, { engine: "typst", formats: ["image"] })).toBe(false);
    expect(supportsTemplate(native, { engine: "typst", formats: ["image"] })).toBe(true);
    expect(supportsTemplate(native, { engine: "html", formats: ["image"] })).toBe(false);
  });
  it("网页输出和混合输出都拒绝仅 Typst 的主题", () => {
    expect(supportsTemplate(native, { engine: "typst", formats: ["html"] })).toBe(false);
    expect(supportsTemplate(native, { engine: "typst", formats: ["html", "image"] })).toBe(false);
    expect(supportsTemplate(html, { engine: "typst", formats: ["html"] })).toBe(true);
  });
  it("能力标签区分图片链路与网页入口", () => {
    expect(templateCapabilities(native)).toEqual(["Typst 图片"]);
    expect(templateCapabilities(html)).toEqual(["HTML 图片", "HTML 网页"]);
  });
});
