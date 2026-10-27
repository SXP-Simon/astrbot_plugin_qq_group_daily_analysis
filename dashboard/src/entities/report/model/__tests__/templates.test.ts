import { describe, expect, it } from "vitest";
import { getTemplateCdnUrl } from "../templates";

describe("模板预览使用配置模块校验后的地址", () => {
  it("拼接已规范化的 CDN 根地址", () => {
    expect(getTemplateCdnUrl("HatsuneMiku", "https://fastly.jsdelivr.net")).toBe(
      "https://fastly.jsdelivr.net/gh/SXP-Simon/astrbot_plugin_qq_group_daily_analysis@feat/template-previews-webp-qq-official/assets/HatsuneMiku-demo.webp",
    );
  });
  it("配置无效时不生成远程地址，不偷偷替换默认站点", () => {
    expect(getTemplateCdnUrl("maria", null)).toBeUndefined();
  });
});
